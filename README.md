# aiva-goldenhind

Servicio de ingesta para el bastion EC2 de Aiva.

## Qué hace
- Extrae solo los archivos `EnhancedTransactionReportInclFX...` desde la fuente SFTP de Aiva.
- Los guarda localmente en el bastion.
- Los deja listos para su procesamiento posterior.
- La primera carga toma archivos desde `28/06` en adelante.
- Después, conserva solo los archivos del mes vigente.

## Flujo
1. Se ejecuta el runner de ingesta.
2. Lee la configuración del entorno.
3. Obtiene la credencial desde SSM Parameter Store.
4. Se conecta al SFTP de Aiva.
5. Descarga solo los archivos nuevos y omite los que ya existen en el bastion.
6. Los mueve a almacenamiento local en el bastion.
7. Limpia los archivos de meses anteriores y conserva solo el mes vigente.

## Objetivo
Mantener la extracción aislada en el bastion, sin exponer credenciales ni cambiar el flujo manual existente.
