WhatsApp Group Export
=====================

Exports the members of one of your WhatsApp groups to a CSV file.
No installation needed. Requires Google Chrome or Microsoft Edge on the PC
(Edge is included with Windows 10 and 11).

HOW TO USE
1. Unzip this folder anywhere, e.g. your Desktop.
2. Double-click WhatsAppGroupExport.exe. A black window opens.
   If Windows SmartScreen shows a blue warning, click "More info" and
   then "Run anyway". The file is unsigned, which is why it warns.
3. A QR code appears. On your phone open WhatsApp > Settings >
   Linked devices > Link a device, and scan it.
   If the code looks broken, maximize the window or press Ctrl and minus
   to zoom out until the whole code fits.
4. Your groups are listed with numbers. Type the number and press Enter.
5. The CSV file is saved next to the .exe, named after the group.
   Open it with Excel.

The login is remembered in the .wwebjs_auth folder next to the .exe, so
the next run connects without a QR code. Delete that folder to log out.

COMMAND LINE (optional, from PowerShell in this folder)
  .\WhatsAppGroupExport.exe --list                        show groups only
  .\WhatsAppGroupExport.exe --group "Family"              export by name
  .\WhatsAppGroupExport.exe --group 3 --out members.csv   by number, custom file

CSV COLUMNS
  saved_name      name from your phone address book (empty if not saved)
  profile_name    name the person set on their own WhatsApp profile
  number          phone number with country code, no +
  is_admin        yes for group admins
  in_my_contacts  yes if the number is in your address book
  id              raw WhatsApp id

Some members may have an empty number: WhatsApp hides the numbers of
certain non-contacts behind an internal id, which is kept in the id column.

NOTE
This tool drives WhatsApp Web in a hidden browser. That is not an official
WhatsApp API and is against Meta's terms; accounts are occasionally flagged.
Use it on your own account, occasionally, not on a schedule.
