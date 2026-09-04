# diagrama — deja aquí tu arquitectura

Sube uno o varios archivos **`.drawio`** a esta carpeta
(GitHub web → *Add file → Upload files* → commit a `main`).
Opcional: un `.xlsx` con IPs / segmentos / tamaños / nombres de VM.

Al hacer commit, el workflow **Procesar diagrama**:

1. descifra cada `.drawio` (determinista, sin LLM),
2. genera el Terraform en `stacks/<nombre>/`,
3. **abre un Pull Request**.

El PR dispara **Terraform Validate** (`fmt` · `init` · `validate` · `tflint`) y comenta
el resultado. Ese es el último stage: revísalo y mergea el PR.

> El agente mueve cada diagrama procesado a `stacks/<nombre>/diagrama.drawio`, así que
> esta carpeta queda vacía tras cada ejecución. Para procesar otra arquitectura, sube
> un `.drawio` nuevo aquí.
