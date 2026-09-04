# agente-terraform — infraestructura

Terraform generado por el **agente local** (diagrama draw.io → HCL) y desplegado por GitHub Actions.

## Flujo

1. En Open WebUI subes un `.drawio`. El agente genera el Terraform y **abre un PR** aquí,
   en `stacks/<nombre>/`.
2. El PR dispara **Terraform Plan**: `fmt` · `init -backend=false` · `validate` · `tflint`,
   y comenta el resultado en el PR. (El `plan` real se activa cuando haya Azure — ver abajo.)
3. Revisas el PR. Si está bien, lo mergeas.
4. Para aplicar: pestaña **Actions → Terraform Apply → Run workflow**, indicando el stack.
   El job espera **aprobación manual** en el Environment `production`.

## Activar el `plan`/`apply` reales (cuando tengas Azure)

- Variable de repo `AZURE_ENABLED` = `true`  (Settings → Secrets and variables → Actions → Variables)
- Secrets: `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`
  (de un Service Principal con rol Contributor en la suscripción)
- Backend remoto del estado: añade un bloque `backend "azurerm"` a cada stack
  (Storage Account + container) y quita el `-backend=false` del workflow de plan.
- Environment `production` con **Required reviewers** (para la aprobación del apply).

## Runner

GitHub-hosted `ubuntu-latest`. No hay runner self-hosted.
