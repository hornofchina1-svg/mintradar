---
name: mintradar-check
description: Before an agent mints or pays into a BNB Chain contract, look it up on MintRadar (datt.my) for an automatic safety reading of its verified source - who can move funds, who can change the rules, and whether that control survives a renounce. Read-only, free, no login, no wallet.
homepage: https://datt.my
---

# MintRadar safety lookup

MintRadar reads every BNB Chain block, flags contracts that many wallets are minting right now, and checks each one against
its verified source on Sourcify. The result is a small JSON file per contract that any agent can fetch with one request.

Use it before you send a transaction to a contract you found in a post, a feed or a tweet. It costs nothing and moves nothing.

## Look up one contract

```bash
curl -s https://datt.my/data/kontrak/<address-in-lower-case>.json
```

A 404 means MintRadar has not checked that contract yet. Treat an unchecked contract the same as an unverified one: read
the source yourself before sending anything.

Example answer (shortened):

```json
{
  "address": "0xd4259832ac80ec5e27f9b8eaaa54ac2639497b64",
  "name": "BabyJagent",
  "label": "merah",
  "findings": [
    {"code": "KEKAL_DANA", "function": "withdrawUsdt",
     "text": "A hard-coded address can move funds through withdrawUsdt(), even after the owner renounces."}
  ],
  "privileged_functions": ["renounceAdmin", "withdrawRemaining", "withdrawUsdt"],
  "source": "https://sourcify.dev/server/v2/contract/56/0xd425...?fields=sources,abi"
}
```

## Labels

| label | meaning | what to do |
|---|---|---|
| `merah` (red) | Source not verified, an upgradeable proxy, or a hard-coded address that can move funds | Do not pay into it unless you have read the source and accept that risk |
| `kuning` (yellow) | An owner or a fixed address can change prices, pause, or withdraw | Normal for most mints; read the listed functions before paying |
| `hijau` (green) | Verified, and no privileged function was found | Still not an audit; check the price and supply yourself |

Finding codes: `TIDAK_DISAHKAN` unverified source · `PROKSI` upgradeable proxy · `KEKAL_DANA` hard-coded address moves funds ·
`KEKAL_KUASA` hard-coded address keeps special rights · `OWNER_DANA` owner can withdraw · `OWNER_UBAH` owner can change rules ·
`DILEPASKAN` ownership renounced.

## Everything checked

```bash
curl -s https://datt.my/data/kontrak/index.json        # address, name, label, checked_at for every contract
curl -s https://datt.my/data/stats.json                # latest radar contacts and the paper result
```

Files refresh every 10 minutes. Please fetch at most once a minute.

## Limits

- This is a heuristic over verified source, not an audit. It points at which functions to read.
- It does not judge price, supply or whether anyone will ever buy.
- A green label on a paid mint does not mean you will get your money back.

Source code of the radar and the checker: https://github.com/hornofchina1-svg/mintradar
