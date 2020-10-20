### DevKit for a [CodeSpace](https://www.codespace-game.com) project

Includes:
* DCPU16 translator (WIP)
* DCPU16 decoder
* DCPU16 emulator
* Hardware
  * LEM1802 display (32x12 symbols with customizable font and palette)
  * Generic keyboard
  * 8 thrusters
  * 1 sensor
  
 <img src="https://user-images.githubusercontent.com/5273398/96639370-4d37f880-132a-11eb-8b8f-f6043e1fec41.gif" width="600">

### Features
* Step-by-step execution
* Customizable CPU speed
* Direct access to some hardware not existed in canonical specifications

### Limitations
* Limited support for interruptions and signed operations:
  * MLI, DVI, IFA, IFU, INT, IQA
* Some performance issues for a long running emulations

### Requirements

python 3.6+
Qt packages (depends on platform)

requirements installation: ```python3 -m pip install -r requirements.txt```

### Run

Clear run: 
```python devkit/devkit.py```

Run with specified .bin file
```python devkit/devkit.py --filename somefile.bin```
