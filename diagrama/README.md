# diagrama — deja aquí tu arquitectura

Sube uno o varios archivos **`.drawio`** a esta carpeta
(GitHub web → *Add file → Upload files* → commit a `main`).
Opcional: un `.xlsx` con IPs / segmentos / tamaños / nombres de VM.

Al hacer commit, el workflow **Procesar diagrama** hace todo en un run:

1. descifra cada `.drawio` (determinista, sin LLM),
2. genera el Terraform en `stacks/<nombre>/`,
3. `terraform fmt` + **`fmt`-check · `init` · `validate` · `tflint`**,
4. **abre un Pull Request** con el resultado de la validación.

Ese es el último stage: revisa los `.tf` del PR y mergéalo. (No hace falta ningún PAT.)

> El agente mueve cada diagrama procesado a `stacks/<nombre>/diagrama.drawio`, así que
> esta carpeta queda vacía tras cada ejecución. Para procesar otra arquitectura, sube
> un `.drawio` nuevo aquí.
