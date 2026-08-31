<!-- do not remove -->

## 0.1.0

### New Features

- Load cantrip environment variables from the config directory ([#10](https://github.com/AnswerDotAI/macmage/pull/10)), thanks to [@jph00](https://github.com/jph00)
- Add interactive key wisps ([#9](https://github.com/AnswerDotAI/macmage/pull/9)), thanks to [@jph00](https://github.com/jph00)
- add listen() for streaming live mic input ([#7](https://github.com/AnswerDotAI/macmage/pull/7)), thanks to [@RensDimmendaal](https://github.com/RensDimmendaal)
- Move Cocoa plumbing to fastcocoa and Imp/Swift build helpers to the imp repo, add layout-cache relearn on combo miss, and extend pick keys to 36 items ([#6](https://github.com/AnswerDotAI/macmage/issues/6))
- add cocoa.py pyobjc helpers, badge/tone wisps and key-driven pick, and fix the config watcher collected kqueue ([#5](https://github.com/AnswerDotAI/macmage/issues/5))
- Move macmage to a single asyncio loop on cfloop: async cantrips, wisps, and capture; drop apart and the background-thread arrangement ([#4](https://github.com/AnswerDotAI/macmage/issues/4))
- Run the Carbon event loop on the main thread, add apart() for fresh-process capabilities (snap_py, tell, frontmost), fix the clipboard baseline race ([#3](https://github.com/AnswerDotAI/macmage/issues/3))
- Add Contacts/Calendars/Reminders, Photos, and audio+speech APIs, and route all Imp calls through a new Imp() runner ([#2](https://github.com/AnswerDotAI/macmage/issues/2))
- Add clipboard watching, pick/show panels, and config-failure panel ([#1](https://github.com/AnswerDotAI/macmage/issues/1))
