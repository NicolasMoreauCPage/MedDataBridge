# Source ZIP for deployment

This folder contains a small helper to create a zip archive of the
repository sources suitable for uploading to the server and extracting
to update the running deployment.

Files added:

- `create_source_zip.py`: Create a zip of the repository while excluding
  development artefacts and the large dependency bundles in
  `Deploiement/dependencies-*`.

Usage (from repository root):

```powershell
python Deploiement/create_source_zip.py --output C:\tmp\meddata-source.zip
```

On the server, unpack and replace the sources (example):

```powershell
# on server
cd /opt/meddata-bridge
# backup current sources
mv app app.bak || true
unzip /path/to/meddata-source.zip -d /opt/meddata-bridge
# Restart service
sudo systemctl restart meddata-bridge
```

Notes:
- The script excludes `.git`, virtualenv directories (`venv`, `.venv`),
  `__pycache__`, `node_modules` and `Deploiement/dependencies-*` bundles.
- You may want to verify file permissions and owners after extracting on
  the server (e.g. set the application user as owner).
