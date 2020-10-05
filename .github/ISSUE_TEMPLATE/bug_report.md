---
name: Bug report
about: Create a report to help us improve
title: 'Bug:'
labels: bug
assignees: JurajNyiri

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Run service '...' with parameters '...'
3. Scroll down to '...'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Log**
If applicable, add error logs.

```
Logger: homeassistant.setup
Source: custom_components/tapo_control/init.py:341
First occurred: 18:08:58 (1 occurrences)
Last logged: 18:08:58

Error during setup of component tapo_control
Traceback (most recent call last):
File "/usr/src/homeassistant/homeassistant/setup.py", line 213, in _async_setup_component
result = await task
File "/usr/local/lib/python3.8/concurrent/futures/thread.py", line 57, in run
result = self.fn(*self.args, **self.kwargs)
File "/config/custom_components/tapo_control/init.py", line 341, in setup
tapoConnector = Tapo(host, username, password)
File "/usr/local/lib/python3.8/site-packages/pytapo/init.py", line 29, in init
self.presets = self.getPresets()
File "/usr/local/lib/python3.8/site-packages/pytapo/init.py", line 430, in getPresets
return self.getPresets(True)
File "/usr/local/lib/python3.8/site-packages/pytapo/init.py", line 427, in getPresets
raise Exception("Error: "+self.getErrorMessage(data['error_code'])+" Response:" + json.dumps(data))
Exception: Error: -1337 Response:{"error": "Not enough pixels!!", "error_code": -1337}
```

**Camera (please complete the following information):**
 - Device Model: [e.g. C200]
 - FW: [e.g. 1.0.14 Build 200720 Rel.38552n(4555)]

**Additional context**
Add any other context about the problem here.
