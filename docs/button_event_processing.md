 Button events in your workspace are processed through a coordinated mechanism involving the FIX database, the pyEFIS UI, and the hardware/software input layers. Here’s a detailed review of how button events (e.g., `TSBTN11`) are routed and processed, with code references and an end-to-end example.

---

## 1. **Button Definition and Association**

### **Button Configuration**
- Buttons are defined in YAML config files (e.g., `pyefis/config/buttons/*.yaml`), specifying a `dbkey` such as `TSBTN{id}11`.
- The `{id}` placeholder is replaced at runtime with the node ID, making the dbkey unique per device (see fixids.md).

### **Database Key Creation**
- The FIX database is defined in database.yaml, which includes keys like `TSBTN11`.

---

## 2. **Physical and Touchscreen Button Input**

### **Physical Button Input**
- Physical buttons (e.g., via CAN bus or GPIO) are mapped to the same dbkey as the touchscreen button.
- Example: The CAN-FIX plugin (src/fixgw/plugins/canfix/mapping.py) parses CAN messages and updates the FIX database for the relevant dbkey (e.g., `TSBTN11`).

### **Touchscreen Button Input**
- The pyEFIS UI (src/pyefis/instruments/button/__init__.py) creates a `Button` widget, which binds to the dbkey (e.g., `TSBTN11`).

---

## 3. **Event Routing and Processing**

### **A. Physical Button Press**
1. **Hardware Event**: Physical button press is detected (e.g., via CAN or GPIO).
2. **FIX Database Update**: The relevant dbkey (`TSBTN11`) is set to `True` in the FIX database.
   - For CAN: See `getSwitchFunction` in mapping.py.
   - For GPIO: See rpi_button plugin.

### **B. Touchscreen Button Press**
1. **UI Event**: User clicks the on-screen button.
2. **FIX Database Update**: The button widget sets the dbkey (`TSBTN11`) to `True` via `fix.db.set_value`.

---

## 4. **UI Reaction and Action Execution**

### **Button Widget Listens for Changes**
- The `Button` widget connects to the dbkey’s `valueChanged` signal (src/pyefis/instruments/button/__init__.py#L112).
- When the dbkey changes, `dbkeyChanged` is called (src/pyefis/instruments/button/__init__.py#L193).

### **Condition Evaluation and Action Execution**
- `processConditions` (src/pyefis/instruments/button/__init__.py#L237) evaluates the button’s conditions (from config).
- If a condition matches (e.g., `CLICKED eq true`), `processActions` (src/pyefis/instruments/button/__init__.py#L272) is called to execute the configured actions (e.g., change screen, set another dbkey, etc.).

---

## 5. **Example Routing: Pressing TSBTN11**

### **A. Physical Button Press**
1. **Button is pressed** (hardware event).
2. **CAN-FIX plugin** receives the event and updates the FIX database:
   - mapping.py#getSwitchFunction
   - Updates `TSBTN11` in the database.

### **B. Database Notifies UI**
3. **FIX database** emits `valueChanged` for `TSBTN11`.
4. **Button widget** receives the signal:
   - Button.dbkeyChanged
   - Updates its state and calls `processConditions`.

### **C. UI Executes Actions**
5. **Button’s conditions** are evaluated:
   - Button.processConditions
   - If a condition matches (e.g., `CLICKED eq true`), actions are executed.
6. **Actions** (e.g., change screen, set value) are performed:
   - Button.processActions

### **D. Touchscreen Press is Similar**
- The only difference is the event starts in the UI, but the dbkey update and subsequent processing are identical.

---

## 6. **Code References**

- **Button config example** (tests/data/buttons/simple.yaml):
  ```yaml
  type: simple
  text: "Units"
  dbkey: TSBTN{id}11
  ```

- **Button widget initialization** (src/pyefis/instruments/button/__init__.py):
  ````python
  // filepath: src/pyefis/instruments/button/__init__.py
  self._dbkey = fix.db.get_item(self.config['dbkey'].replace('{id}', str(self.parent.parent.nodeID)))
  ````

- **Signal connection** (src/pyefis/instruments/button/__init__.py#L112):
  ````python
  // filepath: src/pyefis/instruments/button/__init__.py
  self._db[key].valueChanged[bool].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))
  ````

- **dbkey change handler** (src/pyefis/instruments/button/__init__.py#L193):
  ````python
  // filepath: src/pyefis/instruments/button/__init__.py
  def dbkeyChanged(self,data):
      ...
      self._button.setChecked(self._dbkey.value) 
      self.processConditions(True)
  ````

- **Condition processing** (src/pyefis/instruments/button/__init__.py#L237):
  ````python
  // filepath: src/pyefis/instruments/button/__init__.py
  def processConditions(self,clicked=False):
      ...
      for cond in self._conditions:
          if 'when' in cond:
              ...
              if pc.pycond(expr)(state=self._db_data) == True:
                  self.processActions(cond['actions'])
  ````

- **Action execution** (src/pyefis/instruments/button/__init__.py#L272):
  ````python
  // filepath: src/pyefis/instruments/button/__init__.py
  def processActions(self,actions):
      for act in actions:
          for action,args in act.items():
              hmi.actions.trigger(action, args)
  ````

---

## 7. **Summary**

- **Button events** (physical or touchscreen) update a dbkey (e.g., `TSBTN11`) in the FIX database.
- **UI widgets** listen for changes to their dbkey and react by evaluating conditions and executing actions.
- **Actions** can include UI updates, database changes, or other system commands.

For more details, see:
- `Button`
- fixids.md
- docs/screenbuilder.md
