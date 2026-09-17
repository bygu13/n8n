# WhatsApp group contacts to CSV

Small Node script that links to your WhatsApp account via QR code, lists your
groups, and writes the members of one group to a CSV file.

It uses [whatsapp-web.js](https://wwebjs.dev/), which drives WhatsApp Web in a
headless browser. This is not an official WhatsApp API and is against Meta's
terms of service; accounts are occasionally flagged. Use it on your own account
only and don't run it in a loop.

## Setup

```bash
cd scripts/whatsapp-group-contacts
npm install        # downloads a Chromium build the first time, ~150 MB
```

Needs Node 18 or newer.

## Use

```bash
node index.js                          # pick a group from a numbered list
node index.js --list                   # just print your groups
node index.js --group "Family"         # export by exact (or unique partial) name
node index.js --group 3                # export the 3rd group in the list
node index.js --group "Family" --out family.csv
```

On the first run a QR code is printed in the terminal. On your phone open
WhatsApp > Settings > Linked devices > Link a device and scan it. The session is
stored in `.wwebjs_auth/` next to the script, so later runs connect directly.
Delete that folder to log out.

## Output

One row per member, sorted by name:

| column | meaning |
| --- | --- |
| `saved_name` | the name in your phone's address book, empty if not saved |
| `profile_name` | the name the member set on their own WhatsApp profile |
| `number` | phone number with country code, no `+` |
| `is_admin` | `yes` for group admins |
| `in_my_contacts` | `yes` if the number is in your address book |
| `id` | the raw WhatsApp id |

The file is UTF-8 with a BOM so Excel opens it with the right characters.

Since 2025 WhatsApp hides phone numbers of some non-contacts behind an internal
id (`...@lid`). The script tries to resolve those to numbers; when it can't, the
`number` column is empty and the `id` column keeps the internal id.

## Windows executable (no Node needed)

A ready-made build is in `release/WhatsAppGroupExport-windows.zip`. Unzip it,
double-click `WhatsAppGroupExport.exe`, scan the QR code and pick a group.
See `release/README.txt` for details. The exe does not ship a browser; it uses
the Chrome, Edge or Brave already installed on the PC (Edge comes with Windows).
Set the `WA_BROWSER` environment variable to a browser path to override.

To rebuild it:

```bash
npm install
npm run build:win      # writes dist/WhatsAppGroupExport.exe
```

The exe is unsigned, so Windows SmartScreen shows a warning on first launch
("More info" > "Run anyway").
