# Building the package for friends

1. `.venv\Scripts\python -m pip install pyinstaller` (once).
2. Build the program folder (about 300 MB, Python not needed on the friends' computers):

   ```
   .venv\Scripts\python -m PyInstaller --noconfirm --clean --onedir --name DuneMarket --console --icon packaging\dune-market.ico --paths src ^
     --collect-all rapidocr_onnxruntime --hidden-import PyQt6.sip --exclude-module tkinter ^
     --exclude-module matplotlib --exclude-module pytest packaging\launch.py
   ```

3. Check it: `dist\DuneMarket\DuneMarket.exe selftest` must print `Self-test OK`.
4. Make the zip with the shared database address and key filled in:

   ```
   powershell -File packaging\make-friend-zip.ps1 -Url "https://<project>.supabase.co" -Key "<anon public key>"
   ```

   The result is `dist\DuneMarket-friends.zip`.

The shared table is created with `docs/remote-schema.sql` (see the project log for the Supabase steps).
