"""add_ftp_sftp_support_and_endpoint_linking

Revision ID: ed0571d621c8
Revises: 340b97a9fc6f
Create Date: 2025-12-26 12:10:15.853904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed0571d621c8'
down_revision: Union[str, Sequence[str], None] = '340b97a9fc6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create ftpconfig table
    op.create_table('ftpconfig',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('host', sa.String(), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, default=21),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('password', sa.String(), nullable=False),
        sa.Column('use_sftp', sa.Boolean(), nullable=False, default=False),
        sa.Column('remote_inbox_path', sa.String(), nullable=False, default='/'),
        sa.Column('remote_outbox_path', sa.String(), nullable=False, default='/'),
        sa.Column('remote_archive_path', sa.String(), nullable=False, default='/archive'),
        sa.Column('remote_error_path', sa.String(), nullable=False, default='/error'),
        sa.Column('local_inbox_path', sa.String(), nullable=True),
        sa.Column('local_outbox_path', sa.String(), nullable=True),
        sa.Column('local_archive_path', sa.String(), nullable=True),
        sa.Column('local_error_path', sa.String(), nullable=True),
        sa.Column('file_extensions', sa.String(), nullable=False, default='.hl7,.txt,.json'),
        sa.Column('file_pattern', sa.String(), nullable=True),
        sa.Column('delete_after_process', sa.Boolean(), nullable=False, default=False),
        sa.Column('passive_mode', sa.Boolean(), nullable=False, default=True),
        sa.Column('timeout', sa.Float(), nullable=False, default=30.0),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=3),
        sa.Column('retry_delay', sa.Float(), nullable=False, default=5.0),
        sa.Column('key_file_path', sa.String(), nullable=True),
        sa.Column('key_passphrase', sa.String(), nullable=True),
        sa.Column('host_key_policy', sa.String(), nullable=False, default='auto-add'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('endpoint_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['endpoint_id'], ['systemendpoint.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ftpconfig_name'), 'ftpconfig', ['name'], unique=False)

    # Add FTP/SFTP columns to systemendpoint
    op.add_column('systemendpoint', sa.Column('ftp_host', sa.String(), nullable=True))
    op.add_column('systemendpoint', sa.Column('ftp_port', sa.Integer(), nullable=True))
    op.add_column('systemendpoint', sa.Column('ftp_username', sa.String(), nullable=True))
    op.add_column('systemendpoint', sa.Column('ftp_password', sa.String(), nullable=True))
    op.add_column('systemendpoint', sa.Column('ftp_use_sftp', sa.Boolean(), nullable=False, default=False))
    op.add_column('systemendpoint', sa.Column('ftp_remote_inbox_path', sa.String(), nullable=True))
    op.add_column('systemendpoint', sa.Column('ftp_remote_outbox_path', sa.String(), nullable=True))
    op.add_column('systemendpoint', sa.Column('ftp_remote_archive_path', sa.String(), nullable=True))
    op.add_column('systemendpoint', sa.Column('ftp_remote_error_path', sa.String(), nullable=True))

    # Add linked_endpoint_id for endpoint associations
    op.add_column('systemendpoint', sa.Column('linked_endpoint_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_systemendpoint_linked_endpoint_id', 'systemendpoint', 'systemendpoint', ['linked_endpoint_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove linked_endpoint_id
    op.drop_constraint('fk_systemendpoint_linked_endpoint_id', 'systemendpoint', type_='foreignkey')
    op.drop_column('systemendpoint', 'linked_endpoint_id')

    # Remove FTP/SFTP columns
    op.drop_column('systemendpoint', 'ftp_remote_error_path')
    op.drop_column('systemendpoint', 'ftp_remote_archive_path')
    op.drop_column('systemendpoint', 'ftp_remote_outbox_path')
    op.drop_column('systemendpoint', 'ftp_remote_inbox_path')
    op.drop_column('systemendpoint', 'ftp_use_sftp')
    op.drop_column('systemendpoint', 'ftp_password')
    op.drop_column('systemendpoint', 'ftp_username')
    op.drop_column('systemendpoint', 'ftp_port')
    op.drop_column('systemendpoint', 'ftp_host')

    # Drop ftpconfig table
    op.drop_index(op.f('ix_ftpconfig_name'), table_name='ftpconfig')
    op.drop_table('ftpconfig')
