# agente-terraform — infraestructura

Terraform generado por el **agente local** (diagrama draw.io → HCL) y validado por GitHub Actions.

## Flujo

1. Subes tu(s) `.drawio` (y un `.xlsx` opcional) a la carpeta **`diagrama/`**
   (GitHub web → *Add file → Upload files* → commit a `main`).
2. El push dispara **Procesar diagrama**: descifra el diagrama (determinista, sin LLM),
   genera el Terraform en `stacks/<nombre>/` y **abre un Pull Request**.
3. El PR dispara **Terraform Validate**: `fmt` · `init -backend=false` · `validate` · `tflint`,
   y comenta el resultado en el PR. **Ese es el último stage** (sin `plan` ni `apply`
   todavía — no hay Azure).
4. Revisas el PR. Si está bien, lo mergeas.

## Cuando haya Azure (más adelante)

- Variable de repo `AZURE_ENABLED` = `true`  (Settings → Secrets and variables → Actions → Variables)
- Secrets: `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`
  (de un Service Principal con rol Contributor en la suscripción)
- Backend remoto del estado: añade un bloque `backend "azurerm"` a cada stack
  (Storage Account + container).
- Se reañade el job `plan` a `terraform-validate.yml` y se usa `terraform-apply.yml`
  (Environment `production` con **Required reviewers** para la aprobación del apply).

## Runner

GitHub-hosted `ubuntu-latest`. No hay runner self-hosted.
