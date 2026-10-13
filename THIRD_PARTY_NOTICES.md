# Third-party notices and provenance

This inventory distinguishes software that talk2ai redistributes (currently
none, apart from talk2ai source) from system dependencies and optional user
downloads. A component is not approved merely because its source code is open.
Every model, voice and binary needs its own recorded provenance.

| Component | Author / official source | Version or revision | SPDX | Delivery and review status | Notices / obligations |
|---|---|---|---|---|---|
| Handy | [CJ Pais / Handy](https://github.com/cjpais/Handy) | user-installed AppImage | MIT | System/user dependency; not redistributed | Preserve MIT copyright/license if redistributed. Handy name and artwork are not licensed by its code license. |
| eSpeak NG | [eSpeak NG contributors](https://github.com/espeak-ng/espeak-ng) | distro package | GPL-3.0-or-later | Required system dependency; Retro profile | Source and license offer/notice required if redistributed. |
| Piper engine | [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | not installed | GPL-3.0-or-later | Adapter/catalog only; no engine, model or voice is distributed or enabled | Any future distribution must preserve GPL notices and separately clear each weight. |
| Piper DaveFX / Sharvard / Carlfm weights | upstream voice repositories | not installed | **unverified per weight** | Blocked | Dataset licences do not prove rights over exported ONNX weights. Do not download, bundle or select. |
| Kokoro-82M v1.0 weights and `voices-v1.0.bin` | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), converted release [model-files-v1.1](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1) | `kokoro-v1.0.int8.onnx`, `voices-v1.0.bin` | Apache-2.0 (upstream claim; release audit still required) | Optional explicit user download, never committed to this repository; profiles remain unavailable | Include Apache-2.0 and upstream NOTICE if one accompanies the delivered artifact; retain copyright, patent and attribution notices. Hashes and URLs are in `config/tts-artifacts.json`. The listed voices must still pass real Spanish synthesis and playback validation. |
| kokoro-onnx | [thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | 0.6.1 | MIT | Optional isolated runtime; not redistributed or installed automatically | Preserve MIT license/copyright on redistribution. The manifest pins this wheel URL/SHA-256 only. Its complete platform-specific transitive lock, hashes, SPDX data and notices are not yet approved, so talk2ai does not install it automatically. |
| ONNX Runtime, NumPy, phonemizer, espeakng-loader | respective package projects | not installed by talk2ai | see their installed distributions | Transitive candidates of kokoro-onnx | Not approved for automatic installation until a platform-specific lock records versions, hashes, SPDX and notices for every wheel. |
| Python | [Python Software Foundation](https://www.python.org/psf/license/) | distro package | Python-2.0 | System runtime | Preserve PSF license on redistribution. |
| PyQt6 / Qt | [Riverbank](https://www.riverbankcomputing.com/software/pyqt/) / [Qt Group](https://www.qt.io/licensing/) | distro package | GPL-3.0-only or commercial / LGPL-3.0-only or GPL | System dependency | Downstream packagers must comply with the actual package licence and Qt notices. |
| python-evdev | [gvalkov/python-evdev](https://github.com/gvalkov/python-evdev) | distro package | MIT | System dependency | Preserve MIT notice if redistributed. |
| ydotool | [ReimuNotMoe/ydotool](https://github.com/ReimuNotMoe/ydotool) | distro package | AGPL-3.0-or-later | System dependency | No copy is shipped; comply if redistributing. |
| xdotool | [jordansissel/xdotool](https://github.com/jordansissel/xdotool) | distro package | BSD-3-Clause | System dependency | Preserve BSD notice if redistributed. |
| xbindkeys | [xbindkeys](https://www.nongnu.org/xbindkeys/) | distro package | GPL-2.0-or-later | System dependency | No copy is shipped; comply if redistributing. |
| SQLite | [SQLite](https://sqlite.org/copyright.html) | distro package | blessing / public-domain dedication | System dependency | Not redistributed by talk2ai. |
| AGY/Gemini CLI and Ollama | their respective providers | user-selected external tooling | not asserted by talk2ai | External service/tool; not redistributed | Their models, names and marks are outside this project and must be reviewed by the user/provider terms. |

## Files and branding audit

- `assets/demo.gif` and `assets/demo.webm` are repository demonstration media;
  their authorship/provenance must be confirmed before a release that
  redistributes them outside this repository.
- `assets/ollama-dark.svg` and the old provider SVG constants are not used by
  the tray after this change. The tray draws neutral `G`/`O` markers instead of
  provider logos. The unused asset is retained pending a separate, explicit
  provenance/removal change and is not a grant to use the Ollama mark.
- Badge names are descriptive links, not licences or endorsements. talk2ai is
  independent from every project listed above.

## Review rule

Before adding or changing any dependency, weight, voice, dataset, image or
icon, record its author, canonical URL, immutable version/revision, SPDX
identifier, SHA-256 where downloadable, redistribution terms and required
copyright/NOTICE text here. Do not turn a blocked catalog entry on until this
record is complete for the exact delivered artifacts.
