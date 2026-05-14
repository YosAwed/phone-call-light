# Raspberry Pi Zero スタンドアロンAPモード設定手順

この文書は、設置場所に既存Wi-Fiネットワークがない場合に、Raspberry Pi Zero W/WH 自体をWi-Fiアクセスポイント化して、Android/Taskerから直接パトランプを制御するための手順です。

この構成では、Raspberry PiがローカルWi-Fi APになります。Android/Taskerはそのネットワークに接続し、PiへHTTPリクエストを送ります。

```text
Androidスマホ / Tasker
  -> Wi-Fi SSID: <AP_SSID>
  -> http://192.168.4.1/call/start
  -> Raspberry Pi Zero W/WH
  -> GPIO17 リレー制御
  -> パトランプ
```

HTTP制御サーバーは Flask や gpiozero を使わずに動かせます。Python標準ライブラリと Raspberry Pi OS の `pinctrl` だけを使うため、PiがAP化後にインターネットへ出られない環境でも動作します。

> `<PI_USER>`, `<AP_SSID>`, `<AP_PASSPHRASE>`, `<USB_IF_ALIAS>`, `<HOSTNAME>` は実環境に合わせて置き換えてください。実際のログイン名、Wi-Fiパスワード、運用中のパスフレーズを公開リポジトリへコミットしないでください。

## 1. USB復旧経路を用意する

`wlan0` をAP化すると、既存Wi-Fi経由のSSH接続は切れます。作業前に Raspberry Pi Zero の USB Ethernet Gadget を有効にしておくと、Wi-Fi設定を失敗してもUSB経由で復旧できます。

SDカードの `bootfs` パーティションをPCで開き、以下を設定します。

### `config.txt`

末尾に追加します。

```text
dtoverlay=dwc2
```

### `cmdline.txt`

`cmdline.txt` は必ず1行のまま編集します。次を追加します。

```text
modules-load=dwc2,g_ether
```

必要ならUSB側の固定IPv4も追加します。

```text
ip=10.0.0.2::10.0.0.1:255.255.255.0:<HOSTNAME>:usb0:off
```

Windows側の例です。PowerShellを管理者として起動して実行します。

```powershell
New-NetIPAddress -InterfaceAlias "<USB_IF_ALIAS>" -IPAddress 10.0.0.1 -PrefixLength 24
```

接続例です。

```powershell
ssh <PI_USER>@10.0.0.2
```

固定IPv4を使わない場合は、IPv6リンクローカル経由で次の形式が使えることもあります。

```powershell
ssh <PI_USER>@<HOSTNAME>.local
```

ただし、デバッグや復旧作業では固定IPv4の方が扱いやすいです。

## 2. AP用パッケージをインストールする

`hostapd` と `dnsmasq` のインストール時だけ、Piがインターネットへ出られる必要があります。

PiがUSB接続だけで孤立している場合は、一時的に通常のWi-Fiへ戻すか、Windows側のインターネット接続共有を使ってください。

```bash
sudo apt update
sudo apt install -y hostapd dnsmasq
```

## 3. NetworkManagerにwlan0を触らせない

`nmcli` の hotspot/AP モードは、環境によって `supplicant-timeout` で失敗することがあります。Wi-FiチップがAPモードに対応していても起きます。その場合は `hostapd` を直接使う方が安定します。

```bash
sudo mkdir -p /etc/NetworkManager/conf.d

sudo tee /etc/NetworkManager/conf.d/unmanaged-wlan0.conf >/dev/null <<'EOF'
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF

sudo systemctl restart NetworkManager
```

確認します。

```bash
nmcli device status
```

`wlan0` が `unmanaged` になっていればOKです。

## 4. wlan0に固定IPを付ける

手動テストでは以下を実行します。

```bash
sudo ip link set wlan0 down
sudo ip addr flush dev wlan0
sudo ip addr add 192.168.4.1/24 dev wlan0
sudo ip link set wlan0 up
```

再起動後も自動設定したい場合は、`/etc/systemd/system/patlamp-wlan0.service` を作ります。

```ini
[Unit]
Description=Configure wlan0 for Phone Call Light AP
Before=hostapd.service dnsmasq.service
After=NetworkManager.service

[Service]
Type=oneshot
ExecStart=/bin/ip link set wlan0 down
ExecStart=/bin/ip addr flush dev wlan0
ExecStart=/bin/ip addr add 192.168.4.1/24 dev wlan0
ExecStart=/bin/ip link set wlan0 up
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

有効化します。

```bash
sudo systemctl enable patlamp-wlan0.service
sudo systemctl restart patlamp-wlan0.service
```

## 5. hostapdを設定する

サンプルをコピーし、`<AP_SSID>` と `<AP_PASSPHRASE>` を実環境用に変更します。

```bash
sudo cp setup/hostapd.conf.example /etc/hostapd/hostapd.conf
sudo nano /etc/hostapd/hostapd.conf
```

`hostapd` が mask されている場合は解除します。

```bash
sudo systemctl unmask hostapd
sudo systemctl daemon-reload
```

起動します。

```bash
sudo systemctl enable --now hostapd
```

確認します。

```bash
systemctl status hostapd --no-pager -l
iw dev
```

`iw dev` に以下のような内容が出ればAPとして動いています。

```text
Interface wlan0
        ssid <AP_SSID>
        type AP
        channel 6
```

## 6. dnsmasqを設定する

サンプルをコピーします。

```bash
sudo cp setup/dnsmasq-patlamp.conf.example /etc/dnsmasq.d/patlamp.conf
sudo systemctl restart dnsmasq
sudo systemctl enable dnsmasq
```

DHCPログを見るには次を使います。

```bash
sudo journalctl -u dnsmasq -f
```

スマホが接続したときに、以下のようなログが出ればDHCPが機能しています。

```text
DHCPDISCOVER
DHCPOFFER
DHCPREQUEST
DHCPACK
```

## 7. apt不要版HTTPコントローラーを入れる

リポジトリを `/home/<PI_USER>/phone-call-light` に配置します。

```bash
chmod +x /home/<PI_USER>/phone-call-light/scripts/patlamp-standalone.py
```

`setup/patlamp.service` 内の `<PI_USER>` を実ユーザー名に置き換えたうえで、systemdへコピーします。

```bash
sudo cp /home/<PI_USER>/phone-call-light/setup/patlamp.service /etc/systemd/system/patlamp.service
sudo systemctl daemon-reload
sudo systemctl enable --now patlamp.service
```

確認します。

```bash
systemctl status patlamp --no-pager
journalctl -u patlamp -f
```

## 8. HTTPエンドポイント

スマホがローカルAPに接続している状態で、以下を叩けます。

```text
GET http://192.168.4.1/             ヘルスチェック
GET http://192.168.4.1/call/start   ランプON
GET http://192.168.4.1/call/end     ランプOFF
GET http://192.168.4.1/on           手動ON
GET http://192.168.4.1/off          手動OFF
GET http://192.168.4.1/status       状態確認JSON
```

## 9. Tasker設定

TaskerのHTTP Requestアクションで以下を呼びます。

```text
着信開始       -> GET http://192.168.4.1/call/start
通話終了/Idle  -> GET http://192.168.4.1/call/end
非常停止       -> GET http://192.168.4.1/off
```

Androidは、このローカルAPに対して「インターネット接続なし」と警告する場合があります。その場合は「このネットワークを使用」「接続を維持」「インターネットなしでも接続」相当の選択をしてください。これを選ばないと、WPA認証後すぐに切断されることがあります。

## 10. 診断コマンド

```bash
rfkill list
iw dev
ip -4 addr show wlan0
ip neigh
systemctl status hostapd dnsmasq patlamp --no-pager
sudo journalctl -u hostapd -n 50 --no-pager
sudo journalctl -u dnsmasq -n 50 --no-pager
sudo journalctl -u patlamp -n 50 --no-pager
```

正常時の目安です。

```text
hostapd: AP-ENABLED
iw dev: type AP, ssid <AP_SSID>
wlan0: 192.168.4.1/24
phone: dnsmasqから192.168.4.xを取得
```

## 11. 安全上の注意

AC100Vなどの商用電源配線は、Raspberry Pi/GPIO側と物理的に分離してください。端子台はカバー付きにし、ケーブルグランドやストレインリリーフで引っ張り対策を行います。AC入力の近くには適切なヒューズを入れてください。

可能なら、AC100V回転灯を直接制御するより、12V/24V DCパトライトと認証済み電源アダプタを使う方が安全です。低電圧側でリレー/MOSFET制御する構成の方が、ケース内配線も保守も楽になります。
