# Hardware Requirements (Draft)

## Electrical
- USB input: 5V SELV nominal, no mains coupling.
- Average device current target: <= 250 mA during steady sampling.
- Peak current budget target: <= 500 mA including sensor startup transients.
- Protection: reverse-polarity/overcurrent strategy documented for USB input.

## Sensing and data
- PM channel: PM2.5 trend sampling at configurable intervals (default 2 s).
- VOC channel: TVOC/eCO2 proxy trend sampling at configurable intervals.
- Temp/humidity context channel for drift interpretation.
- Timestamped local samples with bounded retention and deterministic rollover.

## Mechanical
- Desk/workbench footprint target: <= 120 mm x 120 mm x 80 mm.
- Serviceable enclosure with non-destructive opening.
- Mounting/strain-relief for USB cable and sensor modules.

## Environmental
- Indoor non-condensing operation only.
- Designed for hobby workshop ambient range (documented during bring-up).
- Not for outdoor/weather exposure in MVP.

## Connectivity
- Local network mode preferred for dashboard access.
- USB serial fallback path required for setup/debug/export.
- Offline operation without internet required.

## Cost
- Prototype target: USD 35–60 typical.
- Prototype ceiling: USD 75 excluding host phone/computer, tools, shipping, and tax.
- BOM entries remain planning-only until live sourcing validates MPN, stock, and pricing.
