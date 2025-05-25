## pyEFIS Configuration Flow

### 1. **Entry Point: preferences.yaml.custom**
- The main user-editable configuration file is typically preferences.yaml.custom.
- This file **overrides** settings from `preferences.yaml` and is intended for user customizations.
- You can have variants like preferences.yaml.custom.left, preferences.yaml.custom.right, or preferences.yaml.custom.portrait for different hardware setups (see INSTALLING.md).

### 2. **Includes Section**
- The `includes:` section in `preferences.yaml.custom` defines logical names (e.g., `MAIN_CONFIG`, `SCREEN_CONFIG`, `SCREEN_ANDROID`, etc.) mapped to specific YAML files.
- Example from `preferences.yaml.custom.left`:
  ```yaml
  includes:
    MAIN_CONFIG: main/left.yaml
    SCREEN_CONFIG: screens/dakoata_hawk.yaml
    SCREEN_ANDROID: screens/android.yaml
    ...
  ```

### 3. **Main Config**
- The file referenced by `MAIN_CONFIG` (e.g., left.yaml, right.yaml, or portrait.yaml) sets up global parameters:
  - Network settings (`FixServer`, `FixPort`)
  - Screen geometry (`screenWidth`, `screenHeight`, `screenFullSize`)
  - Colors, node IDs, etc.

### 4. **Screen List**
- The file referenced by `SCREEN_CONFIG` (e.g., `screens/dakoata_hawk.yaml`) lists which screens to include:
  ```yaml
  include:
    - SCREEN_ANDROID
    - SCREEN_PFD
    - SCREEN_RADIO
    - SCREEN_EMS
  ```
- These names correspond to other entries in the `includes:` section of `preferences.yaml.custom`.

### 5. **Screen Definitions**
- Each screen (e.g., `SCREEN_ANDROID`, `SCREEN_PFD`, etc.) points to a YAML file that defines the layout and widgets for that screen (e.g., `screens/android.yaml`, `screens/pfd.yaml`).
- These files may themselves use `include:` to pull in further sub-configurations (e.g., button layouts, instrument clusters).

### 6. **Instrument and Button Includes**
- Screens can include reusable instrument/button definitions using the `include:` key, as described in screenbuilder.md.
- Example:
  ```yaml
  instruments:
    - type: include,config/includes/side-buttons.yaml
  ```

### 7. **How It’s Loaded**
- The Python code (see `src/pyefis/cfg.py`) recursively loads YAML files, resolving `include:` keys and merging in preferences.
- The GUI is then built dynamically based on the final, merged configuration.

---

## **Summary Diagram**

```
preferences.yaml.custom
   |
   |-- includes:
   |      MAIN_CONFIG --> main/left.yaml
   |      SCREEN_CONFIG --> screens/dakoata_hawk.yaml
   |      SCREEN_ANDROID --> screens/android.yaml
   |      ...
   |
   |-- main/left.yaml: global settings
   |
   |-- screens/dakoata_hawk.yaml:
   |      include:
   |         - SCREEN_ANDROID
   |         - SCREEN_PFD
   |         ...
   |
   |-- screens/android.yaml, screens/pfd.yaml, ...
           |-- may include further instrument/button configs
```

---

## **Key Points**
- **User customizations** go in `preferences.yaml.custom`.
- **Includes** allow modular, reusable configuration.
- **Screen lists** define which screens are available.
- **Each screen** can include further reusable components.
- The **Python loader** merges everything at runtime.

For more details, see README.rst, INSTALLING.md, and screenbuilder.md.