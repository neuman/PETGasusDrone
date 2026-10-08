# PETGasus: build guide

PETGasus is a small 3D-printed quadcopter for an adult and a 10-year-old to build together. It flies by sight (no camera or goggles), mostly indoors and in a calm back yard.

| | |
|---|---|
| Size | 108 × 108 × 15 mm frame, 82 mm motor-to-motor |
| Weight | ~45 g ready to fly (under the FAA's 250 g registration line) |
| Frame | One print in PETG, about 18 g of plastic and ~1.5–2 h. No supports. |
| Soldering | None. The motors plug into the board and the battery lead is already attached. |
| Flight time | ~3.5–4 min per battery (estimate) |
| Prop guards | All four props spin inside ducts |

The frame layout came from a topology optimiser (`tools/run_topopt.py`). It tied each motor to its own duct ring with four ribbed spokes, joined the ducts to each other, and tied that ring to the centre plate. Compared with an ordinary hand-drawn "X" frame of the same footprint, it is about 3.6× stiffer in a crash. Its first vibration mode is 286 Hz against 187 Hz, which keeps it away from the wobble problem that printed frames are known for. These figures come from simulation only. The real tests are below.

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

The total is **$167**. Without items 5 to 7 it is **$148** plus shipping (see the budget note at the end).

**Why the kit instead of individual parts.** The no-solder board and the plug-in motors cost more bought separately ($80) than the whole kit. The kit's board also has no video transmitter, so there is nothing to license or burn out.

**All-Amazon alternative.** Matrix 1S 5-in-1 5A board (B0DQ8FH3VV, $47.99) plus 1102 18000KV motors (B0834P2LSY, $36.79). This costs about $7 more. That board has a video transmitter, which must stay in PIT mode with its antenna on, and a smaller 5 A ESC. Its mounting holes are 26 mm apart, not 25.5 mm, so change `fc_hole_spacing` and rebuild.

**Do not buy** the Amazon "LiteRadio 3" listing B09PV86XXY. It is the FrSky version and cannot talk to this receiver.

**Worth it later.** RadioMaster Pocket ELRS (Amazon B0CG93QM4T, ~$80 plus two 18650 cells) is a radio worth keeping as he gets better.

---

## 2. Before printing: two measurements (5 minutes)

Once the kit arrives, check two numbers with calipers. The frame was sized around them:

- **Flight controller board.** It must be **30 mm square or smaller**. If it is bigger, change `fc_board_side` in `model/petgasus.py` and rebuild. The ducts will move out to make room.
- **Motor.** It must be **14 mm diameter or less** and **13.8 mm tall or less**. The little clip on the bottom of the shaft has to fit a **2.3 mm** hole.

These are claims A3 and A4. When they check out, record them (see section 9).

---

## 3. Print

Open `build/print/frame.3mf` in Snapmaker Orca. `frame.stl` is the same part for other slicers.

For the sealed print package, run `python3 -m nopekit export print-v1` after recording A3 and A4. It writes `out/print-v1/`, which holds the mesh and a print-settings sheet.

- **PETG.** If the spool has been open a while, dry it first. Wet PETG strings inside the ducts.
- 0.4 mm nozzle, 0.2 mm layers, **3 walls**, **100% infill**.
- **No supports.** Nothing on the part needs them: the steepest overhang is 40° and there are no bridges. If the slicer adds supports, turn them off.
- **5 mm brim.** Snip it off afterwards.
- Print it flat side down, as exported.

After printing, run an M1.4 screw in and out of each of the four small posts in the middle. That pre-cuts the threads.

---

## 4. Take the kit apart

Work with the battery unplugged throughout.

1. Pull the props off. Twist gently and lift straight up.
2. Unplug the four motor connectors from the board, then unscrew the board from the stock frame. **Keep its screws.** If they are M1.4 × 4 or longer, they fit the printed posts and you can skip buying item 6.
3. Unscrew the motors from the stock frame. Each has 3 tiny M1.4 × 3 screws; keep all 12.
4. Put the stock frame and canopy in a bag. That is the spare drone.

---

## 5. Assemble

The centre plate has two strap slots, one on the left and one on the right, with their long sides running front to back. The frame is symmetric, so pick either end along the slots as the **front** and mark it with a marker.

1. **Motors.** Set each motor on a round seat with its wire pointing toward the centre. Screw it on from underneath with its three M1.4 × 3 screws. Snug is enough: these screws strip if forced.
2. **Flight controller.** Place the board on the four posts with its **arrow pointing at the front-right duct**. It sits turned 45°, so its corners point between the ducts. That is what lets it fit. Screw it down with four M1.4 screws.
3. **Motor plugs.** Plug each motor into the nearest socket. Which motor goes to which socket gets checked in Betaflight in step 7.
4. **Battery strap.** Thread the strap up through one slot, over the centre plate (under the board), and down through the other slot. The battery hangs **underneath** the frame along the front-back line. Its weight sits low, which makes the drone steadier for a beginner.
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

1. **Setup tab, board alignment.** Set **Yaw = 45** because the board is turned. Tilt and turn the drone in your hand. The 3D model on screen must follow exactly. If it turns the opposite way, use **−45 (315)**. Getting this wrong flips the drone on its first takeoff, so check it twice.
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

Simulation says the design works. These tests on the real drone are what prove it. Record each result in your own terminal; it is your observation, so the AI can't record it for you. Photos make good evidence.

| Test | What to do | Pass |
|---|---|---|
| **P4** Fit | Board, motors, props and battery fitted. Spin each prop by hand. | Nothing touches |
| **P3** Setup | Betaflight checks in section 7 | All four motors in the right place and direction; 3D model follows the drone |
| **P5** Thrust | Strap the drone upside down to a kitchen scale. Motors tab, all four at 100% for 2 s. | Scale reading ≥ 3 × the drone's weight |
| **P2** Hover | Hover for 30 s at 1 m | No buzzing or wobble; motors only warm |
| **P1** Crash | Bare frame, 5 drops from 2 m onto a hard floor | No cracks or white stress marks |

```sh
export PYTHONPATH=~/.claude/plugins/cache/nopekit/nopekit/a00d0e5da19d/src
python3 -m nopekit claim physical P4 pass --evidence photos/p4.jpg --detail "props spin free"
python3 -m nopekit claim physical A4 assume     # after measuring the board
```

For the full picture of what is checked, what is assumed and what is still unknown, see `REPORT.md`, or run `python3 -m nopekit site serve`.

---

## Budget note

The full list comes to $167, against a $150 target. Ways to get under $150:

- **Skip the strap.** A rubber band holds a 1S battery fine to start with.
- **Skip the spare props.** The kit includes a set, but kids break props.
- **Skip the screws.** This works if the kit's board screws turn out to be M1.4 × 4 or longer.

With all three skipped the total is **$148 plus BetaFPV's shipping**, which is not published.

The project's budget check (claim C10) stays red until you choose: either drop lines from `bom/bom.json` or raise the budget.
