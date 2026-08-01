AICC MANUAL SYNC BUTTON V6

Adds a button named: المزامنة
next to the existing Approve button.

Flow:
Analyze -> Approve -> click المزامنة -> record is sent to platform Books.

Install in the AICC GitHub project root:
- patch_manual_sync_button_v6.py
- Dockerfile (overwrite)

No new site file is required if the current
/htdocs/api/aicc_import_saved_record.php
from V4/V5 is already installed.

After Render becomes Live, press Ctrl+F5 on AICC.
