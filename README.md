# Phone Call Light System

Androidスマホに着信があったとき、Raspberry PiでパトランプをONにするシステムです。

## 必要なもの

### ハードウェア
- Raspberry Pi Zero 2 W（または他のRaspberry Pi）
- microSDカード 16GB以上
- 5V電源アダプタ
- 5V 1chリレーモジュール
- AC100V パトランプ
- ジャンパーワイヤー（メス-メス）3本

### ソフトウェア
- Raspberry Pi OS Lite（64bit推奨）
- Python 3.11+
- Tasker（Androidアプリ、有料）

---

## 配線図（100Vパトランプ + 5Vリレー前提）

> ⚠️ **重要**: AC100V配線は感電・火災の危険があります。ブレーカー/コンセントを確実に遮断し、必要なら有資格者に依頼してください。裸電線の露出や絶縁不良は厳禁です。

### 1) GPIO制御部（3.3Vロジックと5Vリレーの整合）

Raspberry PiのGPIOは3.3Vなので、**リレーコイルの直結駆動は不可**です。  
実装は次のどちらかにしてください。

- **A. 3.3V入力対応のリレーモジュールを使う**（推奨・最短）
  - モジュール内にトランジスタ/ダイオードが実装済みのことが多いです。
  - 仕様に `IN-HIGH >= 2.0V` など3.3Vで確実にONできる条件があるか確認してください。
- **B. 裸の5Vリレーを使う場合は外付けドライバを組む**
  - **NPNトランジスタ + ベース抵抗 + プルダウン抵抗 + フライバックダイオード**を使います。

以下は **B の例** です。

```text
Raspberry Pi                     リレー駆動回路 (5V)
────────────                     ─────────────────────────────
GPIO 17 (Pin11) ──[1k〜4.7k]──→ Base (NPN: 2N2222等)
                         │
                    [10k]→ GND   (プルダウン)

GND (Pin6)  ────────────────→ Emitter (NPN) / リレー電源GND
5V  (Pin2)  ────────────────→ リレーコイル片側

NPN Collector ─────────────→ リレーコイル反対側

フライバックダイオード (1N4007等):
  カソード(線あり側) → 5V側
  アノード           → Collector側
```

- 抵抗2本の考え方（制御用+プルダウン）は妥当です。
- 5Vリレーモジュールを使う場合でも、**「3.3V入力対応」かどうか**を仕様で確認してください。
- GNDはRaspberry Piとリレー電源で**共通化**が必要です。
- リレーコイル電源は、可能ならRaspberry Pi本体とは別系統の安定した5V電源を使い、GNDのみ共通化してください。

### 2) リレー接点側（AC100Vパトランプ）

```text
AC100V(L) ── COM (リレー)
NO (リレー) ── パトランプL
AC100V(N) ──── パトランプN
```

- リレー接点の定格（電圧/電流）がパトランプ負荷を満たすことを確認してください。
- AC側配線は圧着端子・絶縁カバー・ケース収納で、裸配線を残さないでください。

---

## Raspberry Pi セットアップ

### 1. OSインストール
[Raspberry Pi Imager](https://www.raspberrypi.com/software/) でRaspberry Pi OS Liteを書き込む。  
書き込み時に以下を設定:
- Wi-Fi SSID / パスワード
- SSH有効化
- ユーザー名: `pi`

### 2. プロジェクトのインストール
```bash
# Raspberry Piにファイルをコピー
scp -r phone-call-light/ pi@raspberrypi.local:~/

# SSHで接続してインストール
ssh pi@raspberrypi.local
chmod +x ~/phone-call-light/setup/install.sh
~/phone-call-light/setup/install.sh
```

### 3. IPアドレスの確認
```bash
hostname -I
# 例: 192.168.1.100
```

---

## Tasker設定（Android）

着信を検知してRaspberry PiにHTTPリクエストを送ります。

### プロファイル1: 着信時にランプON

**トリガー**
- 種類: `状態 → 電話 → 電話の状態`
- 状態: `着信中`

**タスク: Call Start**
1. `ネット → HTTP リクエスト`
   - メソッド: `POST`
   - URL: `http://192.168.1.100:5000/call/start`（RasPiのIPに変更）
   - ヘッダー: `X-Auth-Token: change-me-please`（設定したトークンに変更）
   - Content-Type: `application/json`
   - Body: `{"caller": "%CNUM"}`

### プロファイル2: 通話終了時にランプOFF

**トリガー**
- 種類: `状態 → 電話 → 電話の状態`
- 状態: `アイドル`

**タスク: Call End**
1. `ネット → HTTP リクエスト`
   - メソッド: `POST`
   - URL: `http://192.168.1.100:5000/call/end`
   - ヘッダー: `X-Auth-Token: change-me-please`

---

## 動作確認

Raspberry Piにて:
```bash
# サーバーの状態確認
sudo systemctl status phone-call-light

# ログをリアルタイムで確認
journalctl -u phone-call-light -f

# 手動でランプONテスト（同じLAN内のPCから）
curl -X POST http://192.168.1.100:5000/call/start \
  -H "X-Auth-Token: change-me-please"

# ランプOFF
curl -X POST http://192.168.1.100:5000/call/end \
  -H "X-Auth-Token: change-me-please"
```

---

## 設定変更

`config.py` で以下を変更できます:

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `RELAY_PIN` | `17` | GPIOピン番号 (BCM) |
| `PORT` | `5000` | サーバーのポート番号 |
| `LAMP_OFF_DELAY` | `3` | 通話終了後にランプが消えるまでの秒数 |

認証トークンは環境変数 `LAMP_AUTH_TOKEN` または `config.py` で設定します。

### セキュリティの推奨設定

- デフォルト値 `change-me-please` は必ず変更してください。
- 例: systemd の override で環境変数を設定

```bash
sudo systemctl edit phone-call-light
```

```ini
[Service]
Environment="LAMP_AUTH_TOKEN=your-long-random-token"
```

その後、以下を実行:

```bash
sudo systemctl daemon-reload
sudo systemctl restart phone-call-light
```

`/status` は `{"status":"ok","simulation":false}` のようなJSONを返します。`simulation` が `true` の場合は GPIO ではなくシミュレーションモードで動作しています。
