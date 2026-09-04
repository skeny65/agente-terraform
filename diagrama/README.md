# diagrama — deja aquí tu arquitectura

Sube uno o varios archivos **`.drawio`** a esta carpeta
(GitHub web → *Add file → Upload files* → commit a `main`).
Opcional: un `.xlsx` con IPs / segmentos / tamaños / nombres de VM.

Al hacer commit, el workflow **Diagrama a Terraform** hace todo en un run:

1. **procesar** — descifra cada `.drawio` (determinista, sin LLM) → `stacks/<nombre>/*.tf` → `terraform fmt` → abre un **Pull Request**
2. **validate** — `fmt`-check · `init` · `validate` · `tflint` → comenta el resultado en el PR
3. **plan** / 4. **apply** — desactivados hasta que haya Azure

Revisa los `.tf` del PR y mergéalo. (No hace falta ningún PAT.)

> El agente mueve cada diagrama procesado a `stacks/<nombre>/diagrama.drawio`, así que esta
> carpeta queda vacía tras cada ejecución. Para procesar otra arquitectura, sube un `.drawio` nuevo.
