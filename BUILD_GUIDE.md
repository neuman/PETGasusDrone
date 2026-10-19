# PETGasus: build guide

PETGasus is a small 3D-printed quadcopter for an adult and a 10-year-old to build together. It flies by sight (no camera or goggles), mostly indoors and in a calm back yard.

| | |
|---|---|
| Size | 111 × 111 × 20 mm frame, 83 mm motor-to-motor |
| Weight | ~44 g ready to fly in PETG, ~42 g in nylon-CF (under the FAA's 250 g registration line) |
| Frame | One print, about 17 g of PETG (14.5 g of nylon-CF) and ~1.5 h, plus supports. |
| Soldering | None. The motors plug into the board and the battery lead is already attached. |
| Flight time | ~3.6 min per battery in PETG, ~3.9 min in nylon-CF (estimates) |
| Prop guards | A low guard round the outer side of each prop, joined into one rim |

The frame's shape came from a 3D topology optimiser. It was told where the motors, props, board, battery and leads go, what must stay empty, and how the frame gets loaded: full thrust, a prop hitting something, the battery, and crashes on the guards from nine directions. It put about 12 g of plastic where those loads go, and the model drew that as one smooth piece with a fillet at every joint. A separate finite-element program (CalculiX) then checked the printed shape for vibration and crashes. These figures come from simulation only. The real tests are below.

---

## 1. Shopping list

Prices were checked on 2026-10-07. Re-check them before ordering.

| # | Item | Where | Price |
|---|---|---|---|
| 1 | **BetaFPV Meteor75 Pro II O4 PNP, ELRS version.** This is a parts donor. It contains the flight controller (Matrix 1S 3-in-1: FC, ESC and ELRS receiver), four 1102 motors on plugs, props, and a stock frame to fall back on if the printed one breaks. | [BetaFPV store](https://betafpv.com/products/meteor75-pro-ii-o4-brushless-whoop-quadcopter) | $79.99 |
| 2 | **BetaFPV LiteRadio 3 ELRS** radio. It also works as a USB joystick for simulators. | [BetaFPV store](https://betafpv.com/products/literadio-3-radio-transmitter) | $32.99 |
| 3 | **BetaFPV LAVA II 1S 320 mAh, BT2.0, 5-pack** | Amazon B0GJSTMT8J | $23.19 |
| 4 | **HOBBYFLY 6-port 1S USB charger (BT2.0)** | Amazon B0FHCVCC1R | $11.99 |
| 5 | Spare Gemfan 1811 45 mm 3-blade props, 1.5 mm shaft, 12-pack | BetaFPV store | $4.99 |
| 6 | M1.4 self-tapping screw assortment that includes M1.4 × 6 (you need 4) | Amazon | ~$8 (estimate) |
| 7 | 10 mm hook-and-loop battery straps | Amazon | ~$6 (estimate) |

The total is **$167**. Without items 5 and 7 it is **$156** plus shipping (see the budget note at the end). Item 6 is not optional: the board's own screws are too short for the printed posts.

**Why the kit instead of individual parts.** The no-solder board and the plug-in motors cost more bought separately ($80) than the whole kit. The kit's board also has no video transmitter, so there is nothing to license or burn out.

**All-Amazon alternative.** Matrix 1S 5-in-1 5A board (B0DQ8FH3VV, $47.99) plus 1102 18000KV motors (B0834P2LSY, $36.79). This costs about $7 more. That board has a video transmitter, which must stay in PIT mode with its antenna on, and a smaller 5 A ESC. Its mounting holes are 26 mm apart, not 25.5 mm, so change `fc_hole_spacing` and rebuild.

**Do not buy** the Amazon "LiteRadio 3" listing B09PV86XXY. It is the FrSky version and cannot talk to this receiver.

**Worth it later.** RadioMaster Pocket ELRS (Amazon B0CG93QM4T, ~$80 plus two 18650 cells) is a radio worth keeping as he gets better.

---

## 2. Before printing: two measurements (5 minutes)

Once the kit arrives, check two parts with calipers. BetaFPV publishes most of their sizes, but not these:

- **Flight controller board.** It is a cross, with a mounting hole at the tip of each arm. The frame was drawn for a cross **40 mm tip to tip or less**, with the four motor sockets under the two side arms, about **12.3 mm** out from the centre. Those numbers come from BetaFPV's photos, not a drawing. If yours differ, change `fc_arm_tip_r` or `socket_y` in `model/petgasus.py` and rebuild.
- **Motor.** BetaFPV's drawing gives 13.8 mm across and 13.6 mm tall. Check that the little clip on the bottom of the shaft fits a **2.3 mm** hole, and that the base under the bell is about **11 mm** across.

These are claims A3 and A4. When they check out, record them (see section 9).

---

## 3. Print

Open `build/print/frame.3mf` in Snapmaker Orca. `frame.stl` is the same part for other slicers.

For the sealed print package, run `python3 -m nopekit export print-v1` after recording A3 and A4. It writes `out/print-v1/`, which holds the mesh and a print-settings sheet.

- **PETG for an everyday print.** A stock U1 prints it with nothing extra. If the spool has been open a while, dry it first: wet filament strings, and it is weaker across its layers.
- **Nylon with carbon fibre (PA6-CF, or PAHT-CF) if you want it to survive hard crashes.** In the simulations it takes two to four times the crash PETG does, is stiffer, and is 2 g lighter. It needs a hardened-steel nozzle, the U1's top cover on, and a spool dried at 80 °C for 8 to 12 hours just before printing. Use the same settings otherwise.
- 0.4 mm nozzle, 0.2 mm layers, **3 walls**, **100% infill**. The limbs are only a few millimetres across.
- **Print it as exported. Do not re-orient it in the slicer.** The model already turned the frame so that the worst crash stress runs along the layers, not across them.
- **Supports ON: tree supports, touching the build plate and the part.** The frame is a curved 3D shape, so its limbs and its rim overhang.
- **Use PLA for the support interface** (the few layers that touch the part), if your printer has two toolheads. PETG does not stick to PLA, so the supports peel off cleanly. Snapmaker's guide "Using a Different Filament for Support (PLA and PETG)" shows how to set it up in Snapmaker Orca.
- **5 mm brim** where the part touches the bed. Snip it off afterwards.

Peel the supports by hand, slowly, from the thin end of each limb towards the thick end. If a support will not come off without bending a limb, stop: that is claim P6 failing. Note where it happened and see section 9.

After printing, run an M1.4 screw in and out of each of the four small posts in the middle. That pre-cuts the threads.

---

## 4. Take the kit apart

Work with the battery unplugged throughout.

1. Pull the props off. Twist gently and lift straight up.
2. Unplug the four motor connectors from the board, then unscrew the board from the stock frame. **Keep its four rubber grommets** (the little rubber balls in its mounting holes). The board's own screws are too short for the printed posts: use four M1.4 × 6 from item 6.
3. Unscrew the motors from the stock frame. Each has 3 tiny M1.4 × 3 screws; keep all 12.
4. Put the stock frame and canopy in a bag. That is the spare drone.

---

## 5. Assemble

The centre of the frame has two strap slots, one on the left and one on the right, with their long sides running front to back. The frame is the same front to back, so pick either end along the slots as the **front** and mark it with a marker.

1. **Motors.** Set each motor on a round seat with its wire pointing toward the centre. Screw it on from underneath with its three M1.4 × 3 screws; there is a clear way up to each one for the screwdriver. Snug is enough: these screws strip if forced.
2. **Flight controller.** Push a rubber grommet into each of the board's four holes. Set the board on the four posts with its **arrow pointing forward**: its front arm points at the front, between the two front hoops. Screw it down through the grommets with four M1.4 × 6 screws, just until the rubber starts to squash.
3. **Motor plugs.** The sockets are **underneath** the board's two side arms, and open sideways. Push each motor's plug into the nearest one from the outside. Which motor goes to which socket gets checked in Betaflight in step 7.
4. **Battery strap.** Thread the strap up through one slot, over the centre (under the board), and down through the other slot. The battery hangs **underneath** the frame along the front-back line, with its plug at the **back**, next to the board's power lead. Its weight sits low, which makes the drone steadier for a beginner.
5. **Props stay off** until the Betaflight checks in step 7 are done.

**Check:** spin each motor by hand. Nothing should rub.

---

## 6. Bind the radio

The kit's receiver runs ExpressLRS (ELRS) 3.4. The LiteRadio 3 runs ELRS 3.0. They share a major version and should bind, but this pairing has not been tested.

1. Turn the radio on.
2. Plug the drone battery in and out three times quickly. The receiver LED blinks fast in bind mode.
3. Use the radio's bind function (see the LiteRadio 3 manual). The LED goes solid when bound.

---

## 7. Betaflight setup (adult; ~20 min; **props OFF**)

Install **Betaflight App** (the configurator) and plug the board into a computer over USB.

1. **Setup tab, board alignment.** The board's arrow points forward, so leave **Yaw = 0**. Tilt and turn the drone in your hand. The 3D model on screen must follow exactly. If it does not, the board is turned: fix the board, not the setting. Getting this wrong flips the drone on its first takeoff, so check it twice.
2. **Motors tab, battery plugged in, props off.** Use **Motor reorder** to click each motor in the order it asks. Then use **Motor direction** to make each one spin the way the diagram shows. Write down which way each one spins.
3. **Modes tab.**
   - **ARM** on a switch.
   - **ANGLE** always on, so the drone self-levels. Do not turn it off until he can hover in place for a whole battery.
   - **Flip over after crash** ("turtle") on another switch. When the drone lands upside down, this flips it back over without walking to it.
4. **Beginner limits.**
   - PID Tuning tab: **Throttle Limit = Scale, 70%**.
   - Rates: lower them so the drone feels calm.
   - Raise both as he improves.
5. **Failsafe.** Arm with props off, then switch the radio off. The motors must stop.
6. **Props on.** Each prop's leading edge must lead in the direction its motor spins. Gemfan props come in two mirror-image types; match them to the directions you wrote down. Props push down on the 1.5 mm shafts.

---

## 8. First flights

- **Practice in a simulator first**, using the radio as a USB joystick. Liftoff and VelociDrone both have a line-of-sight camera mode. A couple of evenings in the sim saves a lot of props.
- Start in a big room or a calm yard, standing behind the drone with both of you facing the same way.
- First goal: hover at knee height for 10 seconds, then land. Next: hover for a whole battery. Then fly slow squares.
- Land when the drone sags or the radio warns about low voltage. Unplug the battery as soon as it lands.

**Batteries (LiPo).** They are safe when treated well. Never charge them unattended, never charge or fly a puffy battery, and store them in a LiPo bag or metal tin. The adult does the charging.

**Rules (US).** Under 250 g and flown for fun, no registration is needed. The adult should pass the free FAA **TRUST** test and carry the certificate. Stay below 400 ft (you will be far below that) and keep the drone in sight.

---

## 9. Testing it, and recording what you find

Simulation says the design flies and fits. For crashes it only gives a floor: CalculiX finds the drop and wall hit at which some point of the frame first reaches the plastic's strength, ignoring how much PETG bends before it cracks. These tests on the real drone are what prove it. Record each result in your own terminal; it is your observation, so the AI can't record it for you. Photos make good evidence.

| Test | What to do | Pass |
|---|---|---|
| **P4** Fit | Board, motors, props and battery fitted. Spin each prop by hand. | Nothing touches |
| **P3** Setup | Betaflight checks in section 7 | All four motors in the right place and direction; 3D model follows the drone |
| **P5** Thrust | Strap the drone upside down to a kitchen scale. Motors tab, all four at 100% for 2 s. | Scale reading ≥ 3 × the drone's weight |
| **P2** Hover | Hover for 30 s at 1 m | No buzzing or wobble; motors only warm |
| **P1** Crash | Bare frame with the motors on. 5 drops from 2 m onto a hard floor, then 5 hits into a wall at a jog (about 3 m/s), guard first | No cracks or white stress marks at the limbs, seats, posts or guards |
| **P6** Supports | Peel the supports off by hand after printing | Every limb whole, no cracks |

```sh
export PYTHONPATH=~/.claude/plugins/cache/nopekit/nopekit/a00d0e5da19d/src
python3 -m nopekit claim physical P4 pass --evidence photos/p4.jpg --detail "props spin free"
python3 -m nopekit claim physical A4 assume     # after measuring the board
```

For the full picture of what is checked, what is assumed and what is still unknown, see `REPORT.md`, or run `python3 -m nopekit site serve`.

---

## Budget note

The full list comes to $167, against a $150 target. Ways to get closer:

- **Skip the strap.** A rubber band holds a 1S battery fine to start with.
- **Skip the spare props.** The kit includes a set, but kids break props.

The screws (item 6) stay: the board's own M1.4 × 5 leave 2.4 mm in the printed posts, under the 3 mm the posts need (claim C8). With both skipped the total is **$156 plus BetaFPV's shipping**, which is not published: still over $150.

The project's budget check (claim C10) stays red until you choose: either drop lines from `bom/bom.json` or raise the budget.
