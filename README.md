# agente-terraform — infraestructura

Terraform generado por el **agente local** (diagrama draw.io → HCL) y procesado por **un único
workflow** de GitHub Actions: `.github/workflows/pipeline.yml`.

## Flujo — 4 stages en un solo workflow ("Diagrama a Terraform")

| # | stage | qué hace | estado |
|---|---|---|---|
| 1 | **procesar** | descifra el/los `.drawio` de `diagrama/` (determinista, sin LLM) → `stacks/<n>/*.tf` → `terraform fmt` → **abre un Pull Request** | activo |
| 2 | **validate** | `fmt`-check · `init -backend=false` · `validate` · `tflint` sobre lo generado → comenta en el PR + Job Summary | activo |
| 3 | **plan** | `terraform plan` real → comenta el plan en el PR | **desactivado** (`vars.AZURE_ENABLED != 'true'` → *Skipped*) |
| 4 | **apply** | `terraform apply` del plan del stage 3 | **desactivado** (Azure + *Run workflow* con `run_apply=true` + aprobar el Environment `production`) |

Uso: sube el `.drawio` a **`diagrama/`** (*Add file → Upload files → commit a `main`*) → pestaña
**Actions** → cuando termine, **revisa el PR y mergéalo**. Alternativa: *Actions → "Diagrama a
Terraform" → Run workflow* y pega el XML en `diagrama_xml`.

> **No hace falta ningún PAT.** Para que el PR se abra solo:
> *Settings → Actions → General → Workflow permissions →*
> **☑ Allow GitHub Actions to create and approve pull requests**.
> Si no está marcado, el stage 1 sube la rama `diagrama/<run_id>` y deja el enlace para abrir el PR.

## Activar los stages 3 y 4 (cuando haya Azure)

- Variable de repo `AZURE_ENABLED` = `true`  (*Settings → Secrets and variables → Actions → Variables*)
- Secrets `ARM_CLIENT_ID` · `ARM_CLIENT_SECRET` · `ARM_TENANT_ID` · `ARM_SUBSCRIPTION_ID`
  (Service Principal con rol Contributor)
- Bloque `backend "azurerm" { … }` en cada stack (Storage Account + container)
- *Settings → Environments → `production` → Required reviewers* (aprobación del `apply`)

No hay que tocar el YAML: los jobs `plan`/`apply` ya están escritos y *gated* por esas condiciones.

## Runner

GitHub-hosted `ubuntu-latest`. No hay runner self-hosted.
