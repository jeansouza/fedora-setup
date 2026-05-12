# Correção de Power Management - ThinkPad T14 + Fedora 43 + Dock

## Problemas

1. **Wake lento (~1 min)** após screen lock + inatividade
2. **Programas fechados** às vezes após wake (indica hibernate ou crash)
3. **Leitor de impressão digital** (Digital Persona U.R.U 4500) para de funcionar após wake

## Diagnóstico

- Sleep mode atual: `s2idle` (shallow sleep - deep sleep não disponível no hardware)
- GNOME auto-suspend: 15 min de inatividade → suspend (causa o wake lento via dock)
- Fingerprint USB ID: `05ba:000a`, path: `/sys/devices/.../usb3/3-10/`
  - `power/control = auto` → autosuspend ativo, coloca device em mau estado
  - `power/autosuspend_delay_ms = 2000` → suspende após 2s
  - `power/wakeup = disabled`

---

## Passo a Passo das Correções

### PASSO 1 — Desabilitar hibernate (corrige "programas fechados")

Criar o arquivo (como root):

```bash
sudo mkdir -p /etc/systemd/sleep.conf.d
sudo tee /etc/systemd/sleep.conf.d/thinkpad.conf << 'EOF'
[Sleep]
AllowSuspend=yes
AllowHibernation=no
AllowSuspendThenHibernate=no
AllowHybridSleep=no
EOF
```

---

### PASSO 2 — Desabilitar auto-suspend do GNOME (corrige wake lento)

Executar como **usuário normal** (não root):

```bash
# Opção A: Desabilitar suspend automático completamente quando plugado na tomada
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'

# Opção B: Só aumentar o tempo para 30 minutos (mais conservador)
# gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 1800
```

> Com a opção A, o sistema nunca suspende sozinho quando está na tomada (dock).
> Só a tela desliga. Wake é instantâneo porque não há suspend real.

---

### PASSO 3 — Corrigir leitor de impressão digital após wake

#### 3a. Regra udev para desabilitar autosuspend do device

```bash
sudo tee /etc/udev/rules.d/99-fingerprint-pm.rules << 'EOF'
# Digital Persona U.are.U 4500 - desabilita USB autosuspend
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="05ba", ATTR{idProduct}=="000a", \
  ATTR{power/autosuspend}="-1", \
  ATTR{power/control}="on"
EOF
```

Aplicar imediatamente (sem precisar reiniciar):

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Verificar se funcionou:

```bash
cat /sys/bus/usb/devices/3-10/power/control
# Deve mostrar: on
```

#### 3b. Script para reinicializar o leitor após wake do sistema

```bash
sudo tee /usr/lib/systemd/system-sleep/fingerprint-reset.sh << 'EOF'
#!/bin/bash
# Reinicializa o leitor de impressão digital após wake do sistema
if [ "$1" = "post" ]; then
    sleep 2
    for device in /sys/bus/usb/devices/*/; do
        if [ -f "$device/idVendor" ] && [ "$(cat $device/idVendor)" = "05ba" ]; then
            if [ -f "$device/idProduct" ] && [ "$(cat $device/idProduct)" = "000a" ]; then
                DEVPATH=$(basename "$device")
                echo "$DEVPATH" > /sys/bus/usb/drivers/usb/unbind 2>/dev/null
                sleep 1
                echo "$DEVPATH" > /sys/bus/usb/drivers/usb/bind 2>/dev/null
            fi
        fi
    done
    systemctl restart fprintd.service 2>/dev/null
fi
EOF

sudo chmod +x /usr/lib/systemd/system-sleep/fingerprint-reset.sh
```

---

## Resumo dos arquivos criados

| Arquivo | O que faz |
|---------|-----------|
| `/etc/systemd/sleep.conf.d/thinkpad.conf` | Desabilita hibernate e hybrid sleep |
| `/etc/udev/rules.d/99-fingerprint-pm.rules` | Mantém leitor USB sempre ativo (sem autosuspend) |
| `/usr/lib/systemd/system-sleep/fingerprint-reset.sh` | Rebind do leitor após cada wake do sistema |

---

## Verificação após aplicar

1. **Fingerprint:** Bloquear tela → esperar 5 min → desbloquear → testar leitor (deve funcionar sem reconectar)
2. **Wake:** Com `sleep-inactive-ac-type = nothing`, a tela só escurece — wake é instantâneo
3. **Programas:** Com hibernate desabilitado, apps não fecham mais. Se ainda acontecer → investigar com:
   ```bash
   journalctl -b -1 --no-pager | tail -100
   ```

---

## Reverter (se precisar desfazer)

```bash
sudo rm /etc/systemd/sleep.conf.d/thinkpad.conf
sudo rm /etc/udev/rules.d/99-fingerprint-pm.rules
sudo rm /usr/lib/systemd/system-sleep/fingerprint-reset.sh
gsettings reset org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type
sudo udevadm control --reload-rules
```
