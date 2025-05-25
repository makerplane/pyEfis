 Physical buttons are associated with touchscreen/software buttons in the pyEFIS project through the use of unique FIX database keys (dbkeys) that are parameterized by a `nodeID`. This mechanism allows both physical and touchscreen buttons to interact with the same logical button state in the system.

### How the Association Works

1. **dbkey Naming Convention with `{id}` Placeholder**  
   In button configuration YAML files, the dbkey for a button is specified using a placeholder `{id}` (e.g., `TSBTN{id}12`).  
   See fixids.md:
   > For example if I put `TSBTN{id}15` as the dbkey for a particular button, on node 1 the dbkey would be `TSBTN115` and node 2 would be `TSBTN215`...

2. **nodeID in Main Config**  
   The `nodeID` is set in the main configuration file (e.g., pyefis/config/main/left.yaml):
   ```yaml
   nodeID: 1
   ```
   This value is used to replace `{id}` in the dbkey at runtime.

3. **Button Widget Initialization**  
   When a `Button` widget is created, it replaces `{id}` in the dbkey with the current node's `nodeID`:
   ````python
   // filepath: src/pyefis/instruments/button/__init__.py
   self._dbkey = fix.db.get_item(self.config['dbkey'].replace('{id}', str(self.parent.parent.nodeID)))
   ````

4. **Physical Button Input**  
   Physical buttons are mapped to the same dbkey as the touchscreen button. When a physical button is pressed, it sets the value of the corresponding dbkey (e.g., `TSBTN115` for node 1, button 15) in the FIX database.

5. **Software Button Reactivity**  
   The software button listens for changes to its dbkey. When the dbkey value changes (either from a touchscreen press or a physical button press), the button's state and actions are updated accordingly.

6. **FIX Database as the Bridge**  
   Both physical and touchscreen buttons interact with the same FIX dbkey, so pressing either one triggers the same logic and UI updates.

### Documentation References

- fixids.md:  
  Explains the `{id}` mechanism and lists the dbkeys for each button.
- docs/screenbuilder.md:  
  Describes how to configure buttons and dbkeys for both physical and touchscreen use.

### Example

If you have a button config:
```yaml
dbkey: TSBTN{id}12
```
And `nodeID: 1`, the actual dbkey becomes `TSBTN112`. Both the physical button (wired to set `TSBTN112` in the FIX database) and the touchscreen button (which sets the same dbkey) will control the same logical button in the UI.

---

**Summary:**  
Physical and touchscreen buttons are associated by sharing a dbkey, parameterized by `nodeID`, so that any input (physical or software) updates the same state in the system. This is handled in the button widget initialization and the FIX database logic. For more, see `Button` and fixids.md.