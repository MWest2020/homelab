---
status: draft
last_reviewed: 2026-07-12
---

# GPU: CUDA UVM-reset

Terugkerende fix voor de situatie waarin de NVIDIA-GPU zichtbaar blijft
(`nvidia-smi` werkt) maar CUDA-workloads falen met een UVM-fout — typisch na
suspend/resume, een driver-update zonder reboot, of nadat een container de GPU
in een slechte staat achterliet.

## Symptomen

- `nvidia-smi` toont de kaart, maar CUDA-programma's geven een fout als
  `CUDA_ERROR_SYSTEM_NOT_READY`, `CUDA_ERROR_UNKNOWN` of een UVM-gerelateerde
  initialisatiefout.
- Containers met GPU-toegang starten niet meer of crashen bij het eerste
  CUDA-call.

## Fix

Herlaad de Unified Virtual Memory-kernelmodule:

```bash
sudo rmmod nvidia_uvm && sudo modprobe nvidia_uvm
```

## Wanneer toepassen

- Alleen als `nvidia-smi` zelf werkt maar CUDA faalt (dan zit het probleem in
  `nvidia_uvm`, niet in de hoofddriver).
- Stop eerst processen/containers die de GPU gebruiken — `rmmod` faalt zolang de
  module in gebruik is (`rmmod: ERROR: Module nvidia_uvm is in use`). Controleer
  met `sudo lsof /dev/nvidia-uvm` of `nvidia-smi`.
- Werkt dit niet, dan is een reboot nodig (of `nvidia_uvm` zit vast in een
  proces dat niet te stoppen is).
