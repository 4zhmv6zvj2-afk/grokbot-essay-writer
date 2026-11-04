## four_way_card
Word copies go to Documents/Essay Bot — OK, another folder, later, or skip.

## four_way_friend
OK runs essay-writer --remember-mac-dir ok (choose_mac_handoff ok) to create Documents/Essay Bot on the Mac. Another needs the folder path before remember-mac-dir. Later or skip without a path stays chat-only; do not say the Mac folder is ready.

## upgrade_reread
After this install or upgrade, read CHANGELOG.txt at the zip root when one is present, then re-read FIRST-RUN.txt and docs/templates/bot.md before student chat. Do not recite install steps to the student.

## first_run_mac
On the Mac at first-run, recommend Documents/Essay Bot for Word and zip copies. The person may confirm that folder, name another path, set this up later, or decline. Later or decline without a path is chat-only: do not invent a Mac copy folder and do not set ESSAY_WRITER_MAC_DIR. Do not say the Mac folder is ready. Both file-work picks call essay_writer.first_run.choose_mac_handoff. When they confirm Documents/Essay Bot, call choose_mac_handoff with ok, or run essay-writer --remember-mac-dir ok. That creates Documents/Essay Bot on the friend's Mac and remembers the path. Stage 1 Confirm on a sequence creates Documents/Essay Bot/<module>/, Documents/Essay Bot/<module>/shared/, and Documents/Essay Bot/<module>/<essay_id>/ for that run's Word and zip copies. When they name another path, call choose_mac_handoff with that folder, or run essay-writer --remember-mac-dir with that folder. That creates the named folder on the Mac and remembers it. Later or skip does not create a folder. Show this card: "Word copies go to Documents/Essay Bot — OK, another folder, later, or skip." Do that before essay-writer --copy-to-mac. essay.setup still refuses unnamed Documents as the cloud save folder. Documents is not the cloud computer.

## ordinary_setup
Ordinary setup collects the Consensus key, the Consensus plan, and the Unpaywall email on the secret card, then passes them to essay.setup.

The Consensus key is for academic research search: it finds papers for the research step. Consensus's help center says the API is how a tool programmatically searches academic research and retrieves relevant papers: https://help.consensus.app/en/articles/16516328-the-consensus-api

Create that key with Consensus's own steps from that page. Click the profile icon in the bottom-left corner, select API & MCP Dashboard, open the Keys and Clients tab, click New key, give the key a name so you can tell what it is for, then create it and copy it somewhere secure. The full key is shown once. If it is lost, revoke it and create a new one. The same path is on https://docs.consensus.app/api-plans-and-access : profile icon, then API & MCP Dashboard, then Keys and clients, then New key. The dashboard named from get-started is https://consensus.app/api-mcp

Ask which Consensus plan they have. Free stores ESSAY_WRITER_CONSENSUS_PAID as 0. Pro stores it as 1. Teams, Deep, and Enterprise use 1, the same paid flag as Pro. Do not add another flag. The published limits are only those on https://docs.consensus.app/api-plans-and-access : Free includes 30 calls a month and the maximum with additional usage is 30; Pro includes 500 and the maximum with additional usage is 1,000. Max papers per request is 20 on Free and 300 on Pro. Pagination past the first page is no on Free and yes on Pro. Full-text excerpts are no on Free and yes on Pro. The rate limit is 1 request per second on Free and 1 request per second on Pro.

The email is for Unpaywall free-PDF lookup. Unpaywall's API docs say a request must include the email as ?email=YOUR_EMAIL, and they ask for at most 100,000 calls a day: https://unpaywall.org/products/api . OpenAlex, from the same team, asks for an email where they can contact you if a script goes wrong, and says that approach is copied from Crossref: https://github.com/ourresearch/openalex-docs/blob/main/how-to-use-the-api/rate-limits-and-authentication.md . Crossref's REST API FAQ answers "Will you spam me with marketing bumf once you have our contact info?" with "No. We will only use it to contact you about problems with your scripts." https://github.com/CrossRef/rest-api-doc/blob/master/README.md . Say that limit, attributed to the Crossref FAQ by way of OpenAlex. Do not say that Unpaywall's own page promised never to email.

If the user skips the Consensus key, the Unpaywall email, or both, show the warning before the skip is accepted. Consensus is not used when the key is missing. Unpaywall free PDF lookup will not run when the email is missing. OpenAlex still runs. After an explicit yes to that warning, call essay.setup with confirmPhase draft, acknowledge_skipped_searches true, and the same other arguments. Show that result. After another explicit yes, call essay.setup with confirmPhase confirm and those same arguments. A confirm that skips without acknowledge_skipped_searches writes nothing.

Do not ask the user to edit a .env file. Do not repeat the key or the email.


## setup_prompt
Set up essay writer. You talk to the user. File work does not own this chat.

Nothing is cloned.

Call essay.setup with confirmPhase draft and no path arguments. Show that result. After an explicit yes, call essay.setup with confirmPhase confirm and the same arguments.

That creates /workspace/Essay-writer/app and /workspace/Essay-writer/KB1, and the folders later steps read under the app: Essay-writer, uploads, and unassigned.

Save on the cloud computer, or on a folder the user names on this computer. Do not use a path the user did not name. Do not fall back to Documents and call it the cloud computer.

Run grok version and include the result. Do not install grok, and do not install it on the Mac.

On the Mac at first-run, recommend Documents/Essay Bot for Word and zip copies. The person may confirm that folder, name another path, set this up later, or decline. Later or decline without a path is chat-only: do not invent a Mac copy folder and do not set ESSAY_WRITER_MAC_DIR. Do not say the Mac folder is ready. Both file-work picks call essay_writer.first_run.choose_mac_handoff. When they confirm Documents/Essay Bot, call choose_mac_handoff with ok, or run essay-writer --remember-mac-dir ok. That creates Documents/Essay Bot on the friend's Mac and remembers the path. Stage 1 Confirm on a sequence creates Documents/Essay Bot/<module>/, Documents/Essay Bot/<module>/shared/, and Documents/Essay Bot/<module>/<essay_id>/ for that run's Word and zip copies. When they name another path, call choose_mac_handoff with that folder, or run essay-writer --remember-mac-dir with that folder. That creates the named folder on the Mac and remembers it. Later or skip does not create a folder. Show this card: "Word copies go to Documents/Essay Bot — OK, another folder, later, or skip." Do that before essay-writer --copy-to-mac. essay.setup still refuses unnamed Documents as the cloud save folder. Documents is not the cloud computer.

Ordinary setup collects the Consensus key, the Consensus plan, and the Unpaywall email on the secret card, then passes them to essay.setup.

The Consensus key is for academic research search: it finds papers for the research step. Consensus's help center says the API is how a tool programmatically searches academic research and retrieves relevant papers: https://help.consensus.app/en/articles/16516328-the-consensus-api

Create that key with Consensus's own steps from that page. Click the profile icon in the bottom-left corner, select API & MCP Dashboard, open the Keys and Clients tab, click New key, give the key a name so you can tell what it is for, then create it and copy it somewhere secure. The full key is shown once. If it is lost, revoke it and create a new one. The same path is on https://docs.consensus.app/api-plans-and-access : profile icon, then API & MCP Dashboard, then Keys and clients, then New key. The dashboard named from get-started is https://consensus.app/api-mcp

Ask which Consensus plan they have. Free stores ESSAY_WRITER_CONSENSUS_PAID as 0. Pro stores it as 1. Teams, Deep, and Enterprise use 1, the same paid flag as Pro. Do not add another flag. The published limits are only those on https://docs.consensus.app/api-plans-and-access : Free includes 30 calls a month and the maximum with additional usage is 30; Pro includes 500 and the maximum with additional usage is 1,000. Max papers per request is 20 on Free and 300 on Pro. Pagination past the first page is no on Free and yes on Pro. Full-text excerpts are no on Free and yes on Pro. The rate limit is 1 request per second on Free and 1 request per second on Pro.

The email is for Unpaywall free-PDF lookup. Unpaywall's API docs say a request must include the email as ?email=YOUR_EMAIL, and they ask for at most 100,000 calls a day: https://unpaywall.org/products/api . OpenAlex, from the same team, asks for an email where they can contact you if a script goes wrong, and says that approach is copied from Crossref: https://github.com/ourresearch/openalex-docs/blob/main/how-to-use-the-api/rate-limits-and-authentication.md . Crossref's REST API FAQ answers "Will you spam me with marketing bumf once you have our contact info?" with "No. We will only use it to contact you about problems with your scripts." https://github.com/CrossRef/rest-api-doc/blob/master/README.md . Say that limit, attributed to the Crossref FAQ by way of OpenAlex. Do not say that Unpaywall's own page promised never to email.

If the user skips the Consensus key, the Unpaywall email, or both, show the warning before the skip is accepted. Consensus is not used when the key is missing. Unpaywall free PDF lookup will not run when the email is missing. OpenAlex still runs. After an explicit yes to that warning, call essay.setup with confirmPhase draft, acknowledge_skipped_searches true, and the same other arguments. Show that result. After another explicit yes, call essay.setup with confirmPhase confirm and those same arguments. A confirm that skips without acknowledge_skipped_searches writes nothing.

Do not ask the user to edit a .env file. Do not repeat the key or the email.

A Consensus key turns Consensus on for the search. No key leaves Consensus off and the search stays on OpenAlex. ESSAY_WRITER_CONSENSUS=0 turns Consensus off. ESSAY_WRITER_CONSENSUS=1 turns it on when a key is present.

Do not write notes or sample files.

If a file-access prompt appears, wait until I allow it, then finish the setup.

When the folders exist, reply with the folder paths and the grok version line. Then stop.


## cursor_setup_prompt
Set up essay writer. You talk to the user. File work does not own this chat.

Nothing is cloned.

Call essay.setup with confirmPhase draft and no path arguments. Show that result. After an explicit yes, and after that sign-in yes when the card was shown, call essay.setup with confirmPhase confirm and the same arguments.

That creates /workspace/Essay-writer/app and /workspace/Essay-writer/KB1, and the folders later steps read under the app: Essay-writer, uploads, and unassigned.

Save on the cloud computer, or on a folder the user names on this computer. Do not use a path the user did not name. Do not fall back to Documents and call it the cloud computer. The worker host is not a save folder.

Run agent --version and include the result. That is the Cursor CLI check. When agent is missing, first-run on the Grok Bot computer installs the Cursor CLI. This check only reports the version, and it never installs on the Mac. Do not install grok.

On the Grok Bot computer, run agent login while the person holds that desktop when they are not already logged in and CURSOR_API_KEY is not on that machine. Show this card before or during login: "I'll sign in to Cursor on my computer. Open my computer and take over. On that screen, choose Allow or Continue. If Google appears, pick the Google account for this Cursor account. Tell me when you're signed in." Tell them Open computer → Take over → I'm done. Use the same Cursor account as Grok Bot. Do not put a key or login URL in chat. Skip that card when agent status shows logged in or CURSOR_API_KEY is already on the machine. After login, run agent status. Wait for that yes before essay.setup confirm.

On the Mac at first-run, recommend Documents/Essay Bot for Word and zip copies. The person may confirm that folder, name another path, set this up later, or decline. Later or decline without a path is chat-only: do not invent a Mac copy folder and do not set ESSAY_WRITER_MAC_DIR. Do not say the Mac folder is ready. Both file-work picks call essay_writer.first_run.choose_mac_handoff. When they confirm Documents/Essay Bot, call choose_mac_handoff with ok, or run essay-writer --remember-mac-dir ok. That creates Documents/Essay Bot on the friend's Mac and remembers the path. Stage 1 Confirm on a sequence creates Documents/Essay Bot/<module>/, Documents/Essay Bot/<module>/shared/, and Documents/Essay Bot/<module>/<essay_id>/ for that run's Word and zip copies. When they name another path, call choose_mac_handoff with that folder, or run essay-writer --remember-mac-dir with that folder. That creates the named folder on the Mac and remembers it. Later or skip does not create a folder. Show this card: "Word copies go to Documents/Essay Bot — OK, another folder, later, or skip." Do that before essay-writer --copy-to-mac. essay.setup still refuses unnamed Documents as the cloud save folder. Documents is not the cloud computer.

Ordinary setup collects the Consensus key, the Consensus plan, and the Unpaywall email on the secret card, then passes them to essay.setup.

The Consensus key is for academic research search: it finds papers for the research step. Consensus's help center says the API is how a tool programmatically searches academic research and retrieves relevant papers: https://help.consensus.app/en/articles/16516328-the-consensus-api

Create that key with Consensus's own steps from that page. Click the profile icon in the bottom-left corner, select API & MCP Dashboard, open the Keys and Clients tab, click New key, give the key a name so you can tell what it is for, then create it and copy it somewhere secure. The full key is shown once. If it is lost, revoke it and create a new one. The same path is on https://docs.consensus.app/api-plans-and-access : profile icon, then API & MCP Dashboard, then Keys and clients, then New key. The dashboard named from get-started is https://consensus.app/api-mcp

Ask which Consensus plan they have. Free stores ESSAY_WRITER_CONSENSUS_PAID as 0. Pro stores it as 1. Teams, Deep, and Enterprise use 1, the same paid flag as Pro. Do not add another flag. The published limits are only those on https://docs.consensus.app/api-plans-and-access : Free includes 30 calls a month and the maximum with additional usage is 30; Pro includes 500 and the maximum with additional usage is 1,000. Max papers per request is 20 on Free and 300 on Pro. Pagination past the first page is no on Free and yes on Pro. Full-text excerpts are no on Free and yes on Pro. The rate limit is 1 request per second on Free and 1 request per second on Pro.

The email is for Unpaywall free-PDF lookup. Unpaywall's API docs say a request must include the email as ?email=YOUR_EMAIL, and they ask for at most 100,000 calls a day: https://unpaywall.org/products/api . OpenAlex, from the same team, asks for an email where they can contact you if a script goes wrong, and says that approach is copied from Crossref: https://github.com/ourresearch/openalex-docs/blob/main/how-to-use-the-api/rate-limits-and-authentication.md . Crossref's REST API FAQ answers "Will you spam me with marketing bumf once you have our contact info?" with "No. We will only use it to contact you about problems with your scripts." https://github.com/CrossRef/rest-api-doc/blob/master/README.md . Say that limit, attributed to the Crossref FAQ by way of OpenAlex. Do not say that Unpaywall's own page promised never to email.

If the user skips the Consensus key, the Unpaywall email, or both, show the warning before the skip is accepted. Consensus is not used when the key is missing. Unpaywall free PDF lookup will not run when the email is missing. OpenAlex still runs. After an explicit yes to that warning, call essay.setup with confirmPhase draft, acknowledge_skipped_searches true, and the same other arguments. Show that result. After another explicit yes, call essay.setup with confirmPhase confirm and those same arguments. A confirm that skips without acknowledge_skipped_searches writes nothing.

Do not ask the user to edit a .env file. Do not repeat the key or the email.

A Consensus key turns Consensus on for the search. No key leaves Consensus off and the search stays on OpenAlex. ESSAY_WRITER_CONSENSUS=0 turns Consensus off. ESSAY_WRITER_CONSENSUS=1 turns it on when a key is present.

Do not write notes or sample files.

If a file-access prompt appears, wait until I allow it, then finish the setup.

When the folders exist, reply with the folder paths and the Cursor CLI version line. Then stop.

