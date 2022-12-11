The [AIDE (Advanced Intrusion Detection Environment)](https://aide.github.io/) software enables integrity checking of installed software.
It works by taking a snapshot of files, storing metadata about them (including hashes), and then comparing with the know values later, when you perform a "check".
When software / files change unexpectedly, this can indicate an attacker is making changes to the system (Intrusion Detection).

**Recommendation:** Install and use AIDE to detect changes to installed software, potentially from attackers.
Run the check at least once per week, and set it up to alert you (via email) when there are changes.

**Note:** AIDE is a bit involved, and you have to make mulitple choices along the way, so this module only helps you with the first step - installing AIDE.
Keep in mind that what AIDE does is quite extensive, it reads many files and performs a lot of logic, so it can be slow.
The commands for initializing a database and performing a check can take several minutes.
Because of this, performing a check every minute or every 5 minutes may be unrealistic.

## Using AIDE

In order to get started with AIDE, you essentially need to perform 4 steps:

1. Install the package:
   * `sudo yum install aide` / `sudo apt install aide`
   * (Or using this module to install it across your infrastructure).
2. Build the "known good state" initial database:
   * `sudo aideinit`
3. Place the database file in the expected location:
   * `sudo cp /var/lib/aide/aide.db.new /var/lib/aide/aide.db`
4. Run checks:
   * `sudo /usr/bin/aide.wrapper --config /etc/aide/aide.conf --check`
   * Add to your CFEngine policy or set up cron to run this daily or weekly
   * Ensure you get alerted by email if it has any unexpected output

Before initializing the database (step 2), you should consider whether this machine is already in a good state - AIDE cannot detect any software that was changed before you initialized it.
As the commands are quite slow, you should decide how often you want to run the check.
Finally, you need to handle updates - after you upgrade packages on the system, AIDE will detect a lot of changes in those packages.
Those changes are of course intentional, and not harmful, but you will have to update (or reinitialize) the database afterwards.

See [appropriate man page](https://linux.die.net/man/1/aide) for more information on AIDE.
