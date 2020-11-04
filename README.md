### DevKit for a [CodeSpace](https://www.codespace-game.com) project

Includes:
* DCPU16 translator (WIP)
* DCPU16 decoder
* DCPU16 emulator
* Hardware
  * LEM1802 display (32x12 symbols with customizable font and palette)
  * Generic keyboard
  * 8 thrusters
  * 2 sensors
  * Door controller
  * Docking clamp controller
  * 2 antennas
  * Generic clock
  
 <img src="https://user-images.githubusercontent.com/5273398/96639370-4d37f880-132a-11eb-8b8f-f6043e1fec41.gif" width="600">

### Features
* Step-by-step execution
* Customizable CPU speed
* Direct access to some hardware not existed in canonical specifications
* ASM code editor with source highlight

### Limitations
* Limited support for interruptions and signed operations:
  * MLI, DVI, IFA, IFU, INT, IQA
* Boot device/Floppy drive/Laser not presented
* No state management for docking clamps 
* Very basic radio support

### Requirements
python 3.6+  

requirements installation: 
```sh
python3 -m pip install -r requirements.txt
```

### Run

Clear run: 
```sh
python3 devkit/devkit.py
```

Run with specified .bin file
```sh
python3 devkit/devkit.py --filename somefile.bin
```

Run with specified .dasm file
```sh
python3 devkit/devkit.py --filename somefile.dasm
```
