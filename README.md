# MintRadar

A read-only radar for free NFT mints on BNB Chain. It reads every block, finds contracts that many different wallets are
minting right now, tells real free mints apart from airdrop spam, and then follows what each one sells for afterwards.

Live data: https://datt.my

The point is to measure before spending. Over the 36 hours to 29 Oct 2026 the radar flagged 290 free or cheap mints.
Minting one of each the moment it was flagged and selling one after 24 hours would have netted about +0.055 BNB on paper,
but only 14 of 93 made money and most of that came from three collections. After 1 hour the same strategy lost money.

## What it does

1. Reads `Transfer` logs from the zero address (an ERC-721 mint) in 25-block chunks.
2. Counts mints and distinct receivers per contract per minute. A contract becomes a contact at 40 mints from 20 wallets
   within 10 minutes (`config.json` → `panas`).
3. Opens six sample mint transactions. Sender keeps the NFT and pays nothing: free mint. One sender spraying NFTs to
   strangers: airdrop.
4. Prices later transfers from the receipt: native BNB, or USDT, USDC and WBNB paid by the buyer or received by the
   seller when an offer is accepted. Transfers to yourself are ignored.
5. Paper result per contract: mint at the flag time, sell at the median sale price inside 1, 6 or 24 hours. No buyer in
   the window counts as the full cost lost.

## Safety check

Every contact is checked against its verified source on Sourcify (`radar/semak.py`): which state-changing functions exist
beyond the standard token ones, who may call them, and whether that control survives a renounce because it is tied to a
hard-coded address. Unverified source is a red flag on its own. It points at what to read; it is not an audit.

## Run it

Python 3.10+ and the standard library only.

```bash
python3 -m unittest discover -s tests          # no network
python3 radar.py imbas                          # scan for ~52 s, run it every minute from cron
python3 radar.py isi-belakang --jam 36          # backfill history (wants an RPC that allows wide eth_getLogs)
python3 radar.py laporan                        # plain-text summary
python3 radar.py awam                           # hidup/data/stats.json for the web page in laman/
```

Data lives in `state/radar.db` (SQLite). Set `MINTRADAR_STATE=/some/dir` to keep test runs out of it.

RPC endpoints are in `config.json`. Free public BSC RPCs reject `eth_getLogs` without an address; the defaults that work
are measured, not guessed (see the notes in `config.json`). Private endpoints go in `state/rpc-peribadi.txt`, one per
line as `<url> <role,role>`, and are never committed.

## Limits

- Prices fall fast. One collection sold for 34 USDT in its first hours and for 0.10 USDT a day later.
- The median sale price is optimistic when everyone sells at the same time.
- Mints gated by a server signature or a puzzle are counted, but a bot copying calldata could not have made them.
- ERC-1155 mints are not scanned yet.

This repository is the radar only. It holds no wallet and sends no transactions.

## Bahasa Melayu

MintRadar ialah radar baca-sahaja untuk free mint NFT di BNB Chain. Ia membaca setiap blok, mencari kontrak yang sedang
dimint oleh banyak wallet berbeza, mengasingkan free mint sebenar daripada airdrop spam, dan menjejak harga jualannya
selepas itu. Data langsung di https://datt.my. Ini ukuran, bukan nasihat: kebanyakan free mint tidak pernah dapat pembeli.

## License

MIT
