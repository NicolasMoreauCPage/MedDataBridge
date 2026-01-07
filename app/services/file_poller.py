"""
File polling service - scans file-based endpoints and processes messages.

Automatically detects message type (HL7 MFN/ADT or HPRIM XML) and routes
to the appropriate handler.
"""


import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from sqlmodel import Session, select
import asyncio

from app.models_shared import SystemEndpoint, MessageLog
from app.models_structure import GHTContext
from app.adapters.filesystem_transport import FileSystemReader
from app.utils.hl7_detector import HL7Detector
from app.services.mfn_importer import import_mfn
from app.services.transport_inbound import on_message_inbound_async

logger = logging.getLogger(__name__)


class FilePollerService:
    """
    Service to poll file-based endpoints and process messages.
    
    Scans inbox directories, detects message type, and routes to:
    - MFN importer for structure messages (HL7)
    - PAM handler for ADT messages (HL7)
    - HPRIM handler for HPRIM XML cotation messages
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.stats = {
            'endpoints_scanned': 0,
            'files_processed': 0,
            'mfn_messages': 0,
            'adt_messages': 0,
            'hprim_messages': 0,
            'unknown_messages': 0,
            'errors': []
        }
    
    @staticmethod
    def _detect_encoding(file_path: Path) -> str:
        """Détecte l'encodage d'un fichier XML en lisant la déclaration XML."""
        try:
            # Lire les premiers 200 bytes en latin-1 (compatible avec tous les encodages)
            raw = file_path.read_bytes()[:200]
            # Chercher la déclaration XML
            match = re.search(br'encoding=["\']([^"\']+)["\']', raw)
            if match:
                encoding = match.group(1).decode('ascii')
                logger.error(f"[ENCODING] {file_path.name}: detected encoding={encoding}")
                return encoding
        except Exception as e:
            logger.error(f"[ENCODING] Error detecting encoding for {file_path.name}: {e}")
        # Encodage par défaut
        logger.error(f"[ENCODING] {file_path.name}: using default UTF-8")
        return 'utf-8'
    
    async def scan_all_file_endpoints(self) -> Dict[str, Any]:
        """
        Scan all enabled FILE endpoints and process pending messages.
        
        Returns:
            dict with processing statistics
        """
        # Find all FILE endpoints that are enabled
        stmt = select(SystemEndpoint).where(
            SystemEndpoint.kind == "FILE",
            SystemEndpoint.is_enabled == True
        )
        endpoints = self.session.exec(stmt).all()
        
        for endpoint in endpoints:
            try:
                await self._scan_endpoint(endpoint)
                self.stats['endpoints_scanned'] += 1
            except Exception as e:
                error_msg = f"Error scanning endpoint {endpoint.name}: {str(e)}"
                self.stats['errors'].append(error_msg)
                print(error_msg)
        
        return self.stats
    
    async def _scan_endpoint(self, endpoint: SystemEndpoint):
        """Scan a single file endpoint"""
        if not endpoint.inbox_path:
            return
        
        # Parse file extensions
        extensions = []
        if endpoint.file_extensions:
            extensions = [ext.strip() for ext in endpoint.file_extensions.split(',')]
        
        # Create file reader
        reader = FileSystemReader(
            inbox_path=endpoint.inbox_path,
            extensions=extensions if extensions else None,
            archive_path=endpoint.archive_path,
            error_path=endpoint.error_path
        )
        
        # Process all pending files
        async def process_message(content: str, file_path: Path) -> bool:
            """Handler function for processing each message"""
            try:
                return await self._process_message(content, file_path, endpoint)
            except Exception as e:
                error_msg = f"Error processing {file_path.name}: {str(e)}"
                self.stats['errors'].append(error_msg)
                logger.error(f"[CALLBACK] {error_msg}", exc_info=True)
                return False
        
        # Process files synchronously but handle async message processing
        result = await self._process_all_files_async(reader, process_message)
        self.stats['files_processed'] += result['processed']
    
    async def _process_all_files_async(self, reader: FileSystemReader, callback):
        """Process all files with async callback support"""
        stats = {'processed': 0, 'failed': 0}
        
        # Get all files (exclude .processing files)
        files = sorted(reader.inbox_path.glob('*'))
        if reader.extensions:
            files = [f for f in files if f.suffix.lower() in reader.extensions]
        files = [f for f in files if f.is_file() and not f.name.endswith('.processing')]
        
        for file_path in files:
            processing_path = None
            try:
                # Rename file to .processing to mark it as being processed
                processing_path = file_path.with_suffix(file_path.suffix + '.processing')
                file_path.rename(processing_path)
                
                # Détecter l'encodage et lire le fichier
                encoding = self._detect_encoding(processing_path)
                content = processing_path.read_text(encoding=encoding)
                success = await callback(content, processing_path)
                
                if success:
                    # Archive the file (remove .processing extension)
                    if reader.archive_path:
                        reader.archive_path.mkdir(parents=True, exist_ok=True)
                        archived_name = file_path.name  # Original name without .processing
                        processing_path.rename(reader.archive_path / archived_name)
                    else:
                        processing_path.unlink()
                    stats['processed'] += 1
                else:
                    # Move to error path (remove .processing extension)
                    if reader.error_path:
                        reader.error_path.mkdir(parents=True, exist_ok=True)
                        error_name = file_path.name  # Original name without .processing
                        processing_path.rename(reader.error_path / error_name)
                    else:
                        # Keep in inbox with .error suffix
                        error_path = file_path.with_suffix(file_path.suffix + '.error')
                        processing_path.rename(error_path)
                    stats['failed'] += 1
            except Exception as e:
                logger.error(f"[FILE_ERROR] Error processing {file_path}: {e}", exc_info=True)
                # If we have a .processing file, move it to error
                current_file = processing_path if processing_path and processing_path.exists() else file_path
                if current_file.exists():
                    if reader.error_path:
                        reader.error_path.mkdir(parents=True, exist_ok=True)
                        error_name = file_path.name  # Original name
                        current_file.rename(reader.error_path / error_name)
                    else:
                        error_path = file_path.with_suffix(file_path.suffix + '.error')
                        current_file.rename(error_path)
                stats['failed'] += 1
        
        return stats
    
    async def _process_message(self, content: str, file_path: Path, endpoint: SystemEndpoint) -> bool:
        """
        Process a single message file using a fresh session.
        
        Creates a new session for each message to avoid session state corruption
        when processing multiple files concurrently. Each message operation is
        isolated to prevent one failure from affecting others.
        
        Supports: HL7 (MFN, ADT) and HPRIM XML messages.
        
        Returns:
            True if successful, False otherwise
        """
        from app.db import engine
        from sqlmodel import Session as SQLModelSession
        
        # Create a fresh session for this message processing
        with SQLModelSession(engine) as msg_session:
            try:
                # Detect if it's HPRIM XML (insensitive à la casse, plusieurs variantes possibles)
                content_stripped = content.strip()
                content_lower = content_stripped.lower()
                is_xml = content_stripped.startswith('<?xml')
                
                # Rechercher hprim dans namespace xmlns ou dans balise racine
                has_hprim = (
                    'hprimxml' in content_lower or 
                    'hprim.org' in content_lower or
                    '<evenementsserveuractes' in content_lower or
                    '<evenementspms' in content_lower or
                    '<evenementsserveurétatspatient' in content_lower
                )
                
                is_hprim = is_xml and has_hprim
                
                # Log détaillé pour diagnostic (forcé en ERROR pour visibilité)
                logger.error(f"[DETECTION] File={file_path.name} is_xml={is_xml} has_hprim={has_hprim} is_hprim={is_hprim}")
                if is_xml:
                    logger.error(f"[DETECTION] {file_path.name} XML content check: lower_has_hprimxml={'hprimxml' in content_lower}, has_hprim_org={'hprim.org' in content_lower}, has_evenements={'evenements' in content_lower[:500]}")
                
                if is_hprim:
                    # Handle HPRIM XML message
                    return await self._handle_hprim(content, file_path, msg_session, endpoint)
                
                # Otherwise, detect HL7 message type
                details = HL7Detector.get_message_type_details(content)
                category = details['category']
                
                # Deduplicate MessageLog by correlation_id, direction, endpoint_id
                msg_log = msg_session.exec(
                    select(MessageLog)
                    .where(MessageLog.correlation_id == details['control_id'])
                    .where(MessageLog.direction == "in")
                    .where(MessageLog.endpoint_id == endpoint.id)
                ).first()
                if msg_log:
                    # Update existing log
                    msg_log.kind = "HL7"
                    msg_log.message_type = f"{details['message_code']}^{details['trigger_event']}" if details['trigger_event'] else details['message_code']
                    msg_log.status = "received"
                    msg_log.payload = content
                    msg_log.created_at = datetime.utcnow()
                else:
                    msg_log = MessageLog(
                        direction="in",
                        kind="HL7",
                        message_type=f"{details['message_code']}^{details['trigger_event']}" if details['trigger_event'] else details['message_code'],
                        endpoint_id=endpoint.id,
                        correlation_id=details['control_id'],
                        status="received",
                        payload=content
                    )
                    msg_session.add(msg_log)
                msg_session.commit()
                
                # Route based on category
                if category == "MFN":
                    return self._handle_mfn(content, msg_log, msg_session, endpoint)
                elif category == "ADT":
                    return await self._handle_adt(content, msg_log, msg_session, endpoint)
                else:
                    self.stats['unknown_messages'] += 1
                    logger.warning(f"Unknown message category '{category}' for file {file_path.name}. Message type: {details.get('message_code')}, trigger: {details.get('trigger_event')}")
                    msg_log.status = "error"
                    msg_log.ack_payload = f"Unknown message category: {category}"
                    msg_session.add(msg_log)
                    msg_session.commit()
                    return False
            except Exception as e:
                # Log the error and mark as failed
                logger.error(f"Error processing message {file_path.name}: {e}", exc_info=True)
                try:
                    # Try to create a MessageLog entry for this error
                    details = HL7Detector.get_message_type_details(content)
                    msg_log = msg_session.exec(
                        select(MessageLog)
                        .where(MessageLog.correlation_id == details['control_id'])
                        .where(MessageLog.direction == "in")
                        .where(MessageLog.endpoint_id == endpoint.id)
                    ).first()
                    if msg_log:
                        msg_log.status = "error"
                        msg_log.ack_payload = f"Processing error: {str(e)}"
                    else:
                        msg_log = MessageLog(
                            direction="in",
                            kind="HL7",
                            endpoint_id=endpoint.id,
                            correlation_id=details.get('control_id'),
                            status="error",
                            payload=content,
                            ack_payload=f"Processing error: {str(e)}"
                        )
                        msg_session.add(msg_log)
                    msg_session.commit()
                except Exception as e2:
                    # If we can't even log the error, rollback and move on
                    logger.error(f"Failed to log error for {file_path.name}: {e2}")
                    msg_session.rollback()
                return False
            return False
    
    def _handle_mfn(self, content: str, msg_log: MessageLog, session: Session, endpoint: SystemEndpoint) -> bool:
        """Handle MFN structure message, robust ACK/error handling"""
        try:
            # Get GHT context for this endpoint
            ght_context = None
            if endpoint.ght_context_id:
                ght_context = session.get(GHTContext, endpoint.ght_context_id)
            if not ght_context:
                stmt = select(GHTContext).where(GHTContext.is_active == True).limit(1)
                ght_context = session.exec(stmt).first()
            if not ght_context:
                raise ValueError("No GHT context available for import")
            # Import MFN structure
            result = import_mfn(content, session, ght_context)
            # Parse HL7 ACK for AE/AR codes (negative ACK)
            ack = str(result) if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
            msa = None
            ack_code = "AA"
            # Try to find MSA segment in ACK (if present)
            if isinstance(content, str):
                lines = content.split('\r')
                msa = next((seg for seg in lines if seg.startswith('MSA|')), None)
                if msa and len(msa.split('|')) > 1:
                    ack_code = msa.split('|')[1]
            # If AE/AR, set error status
            if ack_code in ("AE", "AR"):
                msg_log.status = "error"
                msg_log.ack_payload = f"MFN import negative ACK ({ack_code}): {ack}"
            else:
                msg_log.status = "ack_ok"
                msg_log.ack_payload = f"MFN import completed: {ack}"
            session.add(msg_log)
            try:
                session.commit()
            except Exception as commit_error:
                logger.error(f"MFN commit failed: {commit_error}", exc_info=True)
                session.rollback()
                raise
            self.stats['mfn_messages'] += 1
            return ack_code not in ("AE", "AR")
        except Exception as e:
            self.stats['errors'].append(f"MFN import error: {str(e)}")
            logger.error(f"MFN import error: {e}", exc_info=True)
            
            # Rollback any pending transaction first
            session.rollback()
            
            # Refresh msg_log to get clean state
            try:
                session.refresh(msg_log)
            except:
                pass  # Object may not be in session anymore
            
            msg_log.status = "error"
            msg_log.ack_payload = f"MFN import failed: {str(e)}"
            try:
                session.add(msg_log)
                session.commit()
            except Exception as e2:
                logger.error(f"Failed to save error MessageLog: {e2}")
                session.rollback()
            return False
    
    async def _handle_hprim(self, content: str, file_path: Path, session: Session, endpoint: SystemEndpoint) -> bool:
        """
        Handle HPRIM XML message (cotation data like CCAM, NGAP, UCD, LPP).
        
        HPRIM messages are received for validation and logging but not processed
        for transformation (unlike HL7 which is converted to FHIR/HL7v2).
        They are stored as received and archived.
        """
        correlation_id = None
        try:
            import xml.etree.ElementTree as ET
            
            # Generate a unique correlation ID from the XML (if available)
            try:
                root = ET.fromstring(content)
                # Try to extract message ID from entete namespace element
                ns = {'h': 'http://www.hprim.org/hprimXML'}
                entete = root.find('.//h:enteteMessage', ns)
                if entete is not None:
                    id_elem = entete.find('h:identifiantMessge', ns)
                    if id_elem is not None and id_elem.text:
                        correlation_id = id_elem.text
            except Exception as e:
                logger.debug(f"Could not extract HPRIM message ID: {e}")
            
            # Generate fallback ID if not found
            if not correlation_id:
                correlation_id = f"HPRIM_{datetime.utcnow().isoformat()}"
            
            # Create or update MessageLog
            msg_log = session.exec(
                select(MessageLog)
                .where(MessageLog.correlation_id == correlation_id)
                .where(MessageLog.direction == "in")
                .where(MessageLog.endpoint_id == endpoint.id)
            ).first()
            
            if msg_log:
                msg_log.kind = "HPRIM"
                msg_log.message_type = "HPRIM-XML"
                msg_log.status = "received"
                msg_log.payload = content
                msg_log.created_at = datetime.utcnow()
            else:
                msg_log = MessageLog(
                    direction="in",
                    kind="HPRIM",
                    message_type="HPRIM-XML",
                    endpoint_id=endpoint.id,
                    correlation_id=correlation_id,
                    status="received",
                    payload=content
                )
                session.add(msg_log)
            
            try:
                session.commit()
            except Exception as commit_error:
                logger.error(f"HPRIM msg_log commit failed: {commit_error}", exc_info=True)
                session.rollback()
                raise
            
            # HPRIM messages received via FILE are logged but not processed/transformed
            # (they are for archival/audit purposes)
            msg_log.status = "received"
            msg_log.ack_payload = "HPRIM message received and archived"
            session.add(msg_log)
            try:
                session.commit()
            except Exception as commit_error:
                logger.error(f"HPRIM final commit failed: {commit_error}", exc_info=True)
                session.rollback()
                raise
            
            self.stats['hprim_messages'] = self.stats.get('hprim_messages', 0) + 1
            logger.info(f"HPRIM message processed: {correlation_id}")
            return True
            
        except Exception as e:
            self.stats['errors'].append(f"HPRIM processing error: {str(e)}")
            logger.error(f"HPRIM processing error: {e}", exc_info=True)
            
            # Rollback any pending transaction first
            session.rollback()
            
            try:
                msg_log = MessageLog(
                    direction="in",
                    kind="HPRIM",
                    message_type="HPRIM-XML",
                    endpoint_id=endpoint.id,
                    correlation_id=correlation_id or f"HPRIM_ERROR_{datetime.utcnow().isoformat()}",
                    status="error",
                    payload=content,
                    ack_payload=f"HPRIM processing failed: {str(e)}"
                )
                session.add(msg_log)
                session.commit()
            except Exception as e2:
                logger.error(f"Failed to save error MessageLog for HPRIM: {e2}")
                session.rollback()
            return False
    
    async def _handle_adt(self, content: str, msg_log: MessageLog, session: Session, endpoint: SystemEndpoint) -> bool:
        """Handle ADT PAM message, robust ACK/error handling"""
        try:
            # Use existing PAM handler (async) and pass existing log to avoid duplicates
            ack = await on_message_inbound_async(content, session, endpoint, existing_log=msg_log)
            # Parse HL7 ACK for AE/AR codes (negative ACK)
            msa = None
            ack_code = "AA"
            if isinstance(ack, str):
                lines = ack.split('\r')
                msa = next((seg for seg in lines if seg.startswith('MSA|')), None)
                if msa and len(msa.split('|')) > 1:
                    ack_code = msa.split('|')[1]
            if ack_code in ("AE", "AR"):
                msg_log.status = "error"
                msg_log.ack_payload = f"ADT negative ACK ({ack_code}): {ack}"
            else:
                msg_log.status = "ack_ok"
                msg_log.ack_payload = ack or "ADT processed successfully"
            session.add(msg_log)
            try:
                session.commit()
            except Exception as commit_error:
                # Handle IntegrityError or PendingRollbackError during commit
                logger.error(f"ADT commit failed: {commit_error}", exc_info=True)
                session.rollback()
                # Re-raise to be caught by outer exception handler
                raise
            self.stats['adt_messages'] += 1
            return ack_code not in ("AE", "AR")
        except Exception as e:
            self.stats['errors'].append(f"ADT processing error: {str(e)}")
            logger.error(f"ADT processing error: {e}", exc_info=True)
            
            # Rollback any pending transaction first
            session.rollback()
            
            # Refresh msg_log to get clean state
            try:
                session.refresh(msg_log)
            except:
                pass  # Object may not be in session anymore
            
            msg_log.status = "error"
            msg_log.ack_payload = f"ADT processing failed: {str(e)}"
            try:
                session.add(msg_log)
                session.commit()
            except Exception as e2:
                logger.error(f"Failed to save error MessageLog: {e2}")
                session.rollback()
            return False

def _write_ack_to_file(self, endpoint: SystemEndpoint, correlation_id: str, ack_content: str) -> bool:
        """
        Write an acknowledgment (HL7 ACK, HPRIM ACK) to the ack_path directory.
        
        Creates a file named: {correlation_id}_ACK.txt or .hl7 depending on endpoint config
        
        Returns True if successful, False otherwise
        """
        try:
            if not endpoint.ack_path:
                logger.debug(f"No ack_path configured for endpoint {endpoint.id}, skipping ACK write")
                return True  # Not an error, just not configured
            
            ack_path = Path(endpoint.ack_path)
            ack_path.mkdir(parents=True, exist_ok=True)
            
            # Determine file extension
            ext = ".hl7" if ack_content.startswith("MSH") else ".txt"
            ack_filename = f"{correlation_id}_ACK{ext}"
            ack_file = ack_path / ack_filename
            
            # Write ACK content
            ack_file.write_text(ack_content, encoding='utf-8')
            logger.info(f"ACK written to {ack_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing ACK for endpoint {endpoint.id}: {e}")
            return False

def scan_file_endpoints(session: Session) -> Dict[str, Any]:
    """
    Convenience function to scan all file endpoints.
    
    Args:
        session: SQLModel session
    
    Returns:
        dict with processing statistics
    """
    poller = FilePollerService(session)
    return poller.scan_all_file_endpoints()
