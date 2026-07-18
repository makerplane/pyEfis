# CANaerospace — background and the origins of CAN-FIX

Status: reference (researched 2026-07-05). Companion history for the
CAN-FIX protocol pyEfis/FIX-Gateway ride on; the short version of "why
CAN-FIX exists" is a 2013 statement by Phil Birkelbach, quoted verbatim
in section 4.

## 1. What CANaerospace is

CANaerospace is an application-layer protocol over CAN, created in
**1998 by Michael Stock** of Stock Flight Systems — an aerospace
engineering firm in Farchach (Berg municipality, Bavaria), founded 1993
and specialized in flight-test instrumentation and airborne data
acquisition. Design highlights:

- Big-endian, **self-identifying messages**: 8-byte payload = 4-byte
  header (Node-ID, data type, service code, message code) + 4 bytes of
  data. Half of every frame is metadata.
- CAN identifiers organized into priority-ordered logical channels:
  Emergency Event Data, Node Service High/Low, Normal Operation Data,
  User-Defined High/Low, Debug.
- A standard identifier distribution (IDs 300–1799) for operational
  data — but **alternative distributions may coexist**, and the same
  parameter may be sent with **different data types**.
- Free to download and use; genuinely open for its era.

The flexibility was not an accident: Stock's domain is flight test,
where you want to put arbitrary new parameters on the bus quickly.

## 2. Pedigree — the "larger body of knowledge"

- **NASA AGATE (2001).** NASA published CANaerospace as the databus
  standard of AGATE (Advanced General Aviation Transport Experiments),
  the 1994–2001 NASA/FAA/industry consortium to modernize general
  aviation. That endorsement carried it into research aircraft,
  simulators and UAV programs worldwide.
- **Rotax iS engines (2012–present).** The Rotax 912iS/915iS ECUs speak
  CANaerospace — the protocol ships today in essentially every new
  injected-Rotax installation. (Practical corollary for MakerPlane: a
  FIX-Gateway CANaerospace input plugin would give panels native Rotax
  engine data; the spec is frozen and well documented — a bounded,
  attractive integration target.)
- **ARINC 825 (2007–present).** An AEEC working group — Airbus, Boeing,
  GE, Rockwell Collins, Vector, and Stock Flight Systems itself — used
  CANaerospace as the basis for ARINC 825, the certified-aviation CAN
  standard (29-bit identifiers only; 787/A350-class subsystems; still
  actively revised, later adding CAN FD). The certified world absorbed
  CANaerospace rather than continuing it.

## 3. Current status: frozen, not failed

- The specification's last revision is **V1.7 (2006)** — untouched for
  two decades. There is no active steward for the open spec.
- stockflightsystems.com is still up but is effectively a legacy
  brochure site.
- The commercial product line (Rotax iS Engine Management Unit, MT
  propeller control, CANaerospace loggers) is sold today by
  **RS Flight Systems GmbH** of Berg — the same municipality as
  Farchach, with signs (LinkedIn slug "reiser-flight-systems", shared
  product line) of a Reiser/Stock venture carrying the Stock products
  forward. The exact corporate genealogy is probable, not confirmed.
- So "out of business" is close but not exact: the protocol lives on
  inside Rotax ECUs and (transformed) in ARINC 825; the company faded
  into/behind RS Flight Systems; the open spec is dormant.

## 4. Why CAN-FIX — Birkelbach, August 2013

The primary source is a MakerPlane forum thread, *"What's wrong with
CANaerospace?"* (Aug 2013), where Phil answered exactly this question:

> "With it you can send the same parameter over the bus with different
> data types. This is a great feature if what you are after is
> flexibility. **The problem with flexibility in a communication
> protocol is that it forces complexity at the end points.**"

> "CA also allows for multiple identifier distributions to exist on the
> bus at the same time. It would be up to the end points to determine
> if the data that they are receiving is what they think it is."

> "CAN-FIX is a much more rigid protocol… **There is only one way to
> send airspeed on CAN-FIX.**"

Concretely, CAN-FIX:

- replaced the data-type byte with an **index byte** — up to 256
  instances of a parameter (all your EGTs) instead of type negotiation;
- pinned **one canonical encoding per parameter**, so a $2
  microcontroller needs no type-handling layer;
- put **metadata on the bus** (V-speeds, ranges, alarm setpoints);
- targeted the Experimental/Amateur-Built ecosystem under a Creative
  Commons license.

A fair framing: CANaerospace optimizes for a flight-test lab
(flexibility first); CAN-FIX optimizes for a fixed avionics ecosystem
of heterogeneous cheap nodes (rigidity first). Phil's frustration was a
domain mismatch as much as a design critique — both designs are
rational in their own worlds.

## 5. Family tree

```
Bosch CAN (1986, automotive)
 ├─ CANopen / DeviceNet (industrial)
 ├─ NMEA 2000 (marine — same idea for boats)
 └─ CANaerospace (1998, GA / research / flight test)
     ├─ ARINC 825 (2007, certified transport; CAN FD in later revs)
     ├─ UAVCAN (2014, Kirienko — cites CANaerospace/825 design ideas)
     │   ├─ DroneCAN (2022, continuation of UAVCAN v0)
     │   └─ Cyphal   (2022, continuation of UAVCAN v1)
     └─ CAN-FIX (~2012, MakerPlane — experimental aviation;
                 philosophically the anti-CANaerospace on the
                 flexibility axis)
```

## 6. Assessment: is CAN-FIX the right protocol to standardize on?

(2026-07-05.) **Yes — with precision about what "standardize" means in
this stack.** fix-gateway is the hub, and the FIX key vocabulary — not
any wire protocol — is the real standard. That decomposes the question
into two decisions with very different stakes:

1. **The semantic vocabulary** (which parameters exist, units, ranges,
   metadata). This is where lock-in actually lives, and it is already
   decided by adoption: the FIX key space is CAN-FIX's parameter
   model, and the configurator (V-speed profiles, gauge bands), the
   GCU contract and the instrument-bugs design all ride CAN-FIX
   semantics.
2. **The wire protocol for our own hardware nodes** (GCU head, sensor
   nodes). Nearly free to choose — anything else can be bridged in
   through a fix-gateway plugin, as GDL90/Stratux, X-Plane, GNX-375,
   OnSpeed and the Dynon/MGL/Garmin serial protocols already are.

### The alternatives, honestly

- **CANaerospace** — frozen at V1.7/2006, no steward, and the
  flexibility-at-the-endpoints burden is what CAN-FIX rejected.
  Relevant as an *input*: a CANaerospace plugin yields native Rotax iS
  engine data, and a frozen spec is a pleasant integration target.
  Consume it; don't adopt it.
- **ARINC 825** — paywalled spec, committee governance without an
  E-AB seat, zero experimental-aviation ecosystem. Wrong domain.
- **DroneCAN / Cyphal** — the only serious rival: actively developed,
  strong tooling, cheap COTS nodes (a ~$50 DroneCAN magnetometer is a
  tempting answer to the compass gap). But the semantics are
  drone-centric — no V-speed metadata, no GA engine-instrument
  vocabulary, none of the pilot-facing configuration this ecosystem is
  built on — and Cyphal's DSDL toolchain is heavy for the
  cheap-microcontroller audience CAN-FIX serves. Right relationship:
  **bridge, don't migrate** (a DroneCAN input plugin someday to
  harvest commodity sensors).
- **NMEA 2000** — closed PGN registry, marine semantics. No.

### The slow-moving environment cuts in favor

Aviation buses cement over decades (CANaerospace 1998 → still in every
injected Rotax; CAN-FIX ~2012 → still the MakerPlane bus). In a slow
environment the dominant risk is not being outrun — it is **a standard
dying with its steward**, which is precisely the CANaerospace story.
Against that, CAN-FIX is unusually well positioned for this project:
CC-licensed, multiple open implementations, Birkelbach active, and the
canfix-spec fork (.ods master → generated JSON/XML/RST, live Pages
spec, wiki) is stewardship infrastructure we already operate. A
co-steward seat is unavailable at any price with Cyphal or AEEC. In a
slow environment, owning the vocabulary beats renting a bigger one.

### Practical posture

- **Declare it:** CAN-FIX semantics as the standard; other protocols
  are federated inputs via fix-gateway plugins. (Clean against the IP
  posture: CC license, documented Birkelbach provenance.)
- **Exercise stewardship on real gaps** — e.g. the missing Selected
  Heading parameter surfaced by the instrument-bugs design is a
  natural first spec addition through the fork process.
- **Known ceilings, no action needed yet:** classic CAN 2.0 bandwidth
  (fine for flight/engine data, not video/radar-class payloads) and no
  CAN FD story. If that ever matters, add a second transport bridged
  at fix-gateway — not a protocol migration.
- **Keep two bridge plugins on the roadmap:** CANaerospace-in (Rotax
  iS), DroneCAN-in (commodity sensors).

One-sentence version: the architecture already made the wire protocol
swappable, so standardizing on CAN-FIX costs little even if wrong —
and the stewardship position makes it the only option whose future is
partly in our own hands.

## Sources

- [Wikipedia — CANaerospace](https://en.wikipedia.org/wiki/CANaerospace)
- [MakerPlane forum — "What's wrong with CANaerospace?" (Aug 2013)](http://makerplane.org/forum/viewtopic.php?t=216)
- [CAN-FiX Overview (makerplane.org)](https://makerplane.org/can-fix-overview/)
- [CANaerospace V1.7 specification (PDF)](https://www.stockflightsystems.com/tl_files/downloads/canaerospace/canas_17.pdf)
- [Stock Flight Systems — ARINC 825 presentation (PDF)](https://files.stockflightsystems.com/_5_Arinc_825/ARINC825_Presentation.pdf)
- [arinc-825.com — The ARINC825 Standard](https://www.arinc-825.com/the-arinc825-standard/)
- [Vector application note — CAN-based protocols in Avionics (PDF)](https://cdn.vector.com/cms/content/know-how/_application-notes/canopen/AN-ION-1-0104_CAN-based_protocols_in_Avionics.pdf)
- [RS Flight Systems](https://www.rs-flightsystems.com/)
- [RotaxNews — Stock Instruments EMU for the 915iS](https://rotaxnews.net/?p=965)
- [Wikipedia — Cyphal](https://en.wikipedia.org/wiki/Cyphal)
- [Zubax — Cyphal vs DroneCAN](https://zubax.com/blog/on-the-key-differences-between-cyphal-and-dronecan-formerly-uavcan/2038)
- [Kirienko CANaerospace library README](https://github.com/mjs513/CANaerospace/blob/master/pavel_kirienko-canaerospace/README.md)
