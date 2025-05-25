## Action handlers
In the pyEFIS system are Python functions or methods that execute specific operations in response to actions defined in your YAML configuration files. When a process condition is met (for example, a button is pressed and a condition evaluates to true), the system looks up the corresponding action(s) and invokes the appropriate handler(s) to perform the requested operation.

---

## How Action Handlers Work

### 1. **Definition in YAML**
In your button or instrument YAML config, you define actions under a condition:
```yaml
conditions:
  - when: CLICKED eq true
    actions:
      - set: { key: "ALT", value: 1000 }
      - change_screen: { screen: "main" }
```
Each action (e.g., `set`, `change_screen`) corresponds to a handler in Python.

---

### 2. **Action Triggering in Code**
When a condition is met, the code calls the action trigger mechanism:
````python
def processActions(self, actions):
    for act in actions:
        for action, args in act.items():
            hmi.actions.trigger(action, args)
````

---

### 3. **Action Handler Lookup and Execution**
The `hmi.actions.trigger` function looks up the handler for the action name and calls it with the provided arguments.

Example (simplified):
````python
class Actions:
    def __init__(self):
        self._handlers = {}

    def register(self, name, handler):
        self._handlers[name] = handler

    def trigger(self, name, args):
        if name in self._handlers:
            self._handlers[name](**args)
        else:
            raise Exception(f"No handler for action '{name}'")
````

Handlers are registered at startup or module import time.

---

### 4. **Examples of Action Handlers**
- **set**: Sets a value in the FIX database.
- **change_screen**: Changes the current UI screen.
- **toggle**: Toggles a boolean value.
- **play_sound**: Plays a notification sound.

Each of these is implemented as a Python function and registered with the action system.

---

### 5. **Adding a New Action Handler**
To add a new action:
1. Write a Python function that implements the desired behavior.
2. Register it with the action system using a unique name.
3. Reference the new action name in your YAML config.

---

## **Summary Table**

| Action Name     | Handler Location                        | Example Use in YAML           |
|-----------------|----------------------------------------|-------------------------------|
| set             | hmi/actions.py (`set_handler`)          | `- set: { key: "ALT", value: 1000 }` |
| change_screen   | hmi/actions.py (`change_screen_handler`)| `- change_screen: { screen: "main" }` |
| toggle          | hmi/actions.py (`toggle_handler`)       | `- toggle: { key: "LIGHTS" }`         |

---

**In summary:**  
Action handlers are the Python functions that actually perform the work when an action is triggered by a process condition. They are registered with the action system and invoked automatically based on your YAML configuration. To extend the system, you can add new handlers and reference them in your configs.

