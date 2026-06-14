# Manual de Usuario — STA Muebles y Terminaciones

> Sistema de gestión interna desarrollado en Django 4.2.  
> Panel de administración en `/gestion/` · Sitio público en `/`

---

## Índice

1. [Acceso al sistema](#1-acceso-al-sistema)
2. [Dashboard](#2-dashboard)
3. [Clientes y Facturas Emitidas](#3-clientes-y-facturas-emitidas)
4. [Cuentas por Cobrar](#4-cuentas-por-cobrar)
5. [Proveedores y Facturas Recibidas](#5-proveedores-y-facturas-recibidas)
6. [Cuentas por Pagar y Anticipos](#6-cuentas-por-pagar-y-anticipos)
7. [Proyectos y Control de Costos](#7-proyectos-y-control-de-costos)
8. [Recursos Humanos](#8-recursos-humanos)
9. [Tesorería y Movimientos Bancarios](#9-tesorería-y-movimientos-bancarios)
10. [Plan de Cuentas](#10-plan-de-cuentas)
11. [Contabilidad y Libro Diario](#11-contabilidad-y-libro-diario)
12. [Tributario](#12-tributario)
13. [Usuarios y Roles](#13-usuarios-y-roles)
14. [Sitio Web Público](#14-sitio-web-público)
15. [Relaciones entre módulos](#15-relaciones-entre-módulos)
16. [Ejemplo: flujo contable completo](#16-ejemplo-flujo-contable-completo)

---

## 1. Acceso al sistema

**URL de ingreso:** `http://<servidor>/gestion/login/`

Ingrese su nombre de usuario y contraseña. Si ya está autenticado será redirigido al Dashboard automáticamente. Para cerrar sesión use el botón **Cerrar sesión** en la parte inferior del menú lateral.

> Todas las páginas del panel requieren autenticación. Un intento de acceso sin sesión activa redirige al login.

---

## 2. Dashboard

**Ruta:** `/gestion/dashboard/`

Pantalla principal con los indicadores clave del negocio:

| Sección | Qué muestra |
|---|---|
| **Saldo bancario total** | Suma de saldos actuales de todas las cuentas bancarias activas |
| **Ingresos del mes** | Total de facturas emitidas en el mes en curso |
| **Egresos del mes** | Total de facturas recibidas en el mes en curso |
| **Margen bruto** | Ingresos − Egresos del mes |
| **Cuentas por Cobrar vencidas** | Top 10 CxC con mayor antigüedad pendiente de pago |
| **CxC / CxP pendientes** | Totales globales de cobros y pagos pendientes |
| **Proyectos activos** | Cantidad de proyectos en estado "en ejecución" |
| **F-29 pendientes** | Últimas 3 declaraciones F-29 sin presentar |
| **Gráfico 6 meses** | Barras comparativas ingresos vs. egresos de los últimos 6 meses |

---

## 3. Clientes y Facturas Emitidas

### 3.1 Clientes

**Rutas:** `/gestion/clientes/` · `/gestion/clientes/crear/` · `/gestion/clientes/<pk>/` · `/gestion/clientes/<pk>/editar/`

Cada cliente almacena:

- **RUT** (único, con dígito verificador validado automáticamente)
- Razón social, giro, dirección completa
- Teléfono, email, nombre de contacto
- Estado activo/inactivo
- Notas libres

Desde el **detalle del cliente** se muestran las últimas 10 facturas emitidas.

### 3.2 Facturas Emitidas

**Rutas:** `/gestion/clientes/facturas/` · `.../crear/` · `.../<pk>/` · `.../<pk>/editar/`

Al crear una factura se debe indicar:

| Campo | Obligatorio | Notas |
|---|---|---|
| N° de factura | Sí | Único en el sistema |
| Cliente | Sí | Búsqueda autocomplete |
| Fecha de emisión | Sí | |
| Fecha de vencimiento | No | Si se ingresa, se crea automáticamente una CxC |
| Proyecto asociado | No | |
| Monto neto | Sí | IVA (19%) y total se calculan automáticamente al guardar |
| Estado | — | `Pendiente`, `Pagada`, `Vencida`, `Anulada` |

**IVA y total** son calculados por el modelo: `iva = neto × 0.19`, `total = neto + iva`. Los campos se muestran en el formulario por referencia pero se sobreescriben al guardar.

**Líneas de detalle (DetalleFacturaEmitida):** cada factura puede tener ítems con descripción, cantidad y precio unitario. El subtotal por línea se calcula como `cantidad × precio_unitario`.

---

## 4. Cuentas por Cobrar

**Ruta:** `/gestion/clientes/cxc/`

Se crea automáticamente al registrar una factura emitida con fecha de vencimiento. Registra:

- Monto total y monto pagado
- Saldo pendiente (calculado)
- Estado: `Pendiente`, `Pagada`, `Vencida`, `Incobrable`

**Para marcar como pagada:** en el listado, use el botón **Pagar** junto a cada CxC. Esto registra la fecha de pago (hoy) y cambia el estado de la CxC y de la factura asociada a `Pagada`.

---

## 5. Proveedores y Facturas Recibidas

### 5.1 Proveedores

**Rutas:** `/gestion/proveedores/` · `.../crear/` · `.../<pk>/` · `.../<pk>/editar/`

Datos almacenados: RUT, razón social, giro, dirección, datos bancarios para pago (banco, tipo y número de cuenta), estado activo/inactivo.

### 5.2 Facturas Recibidas

**Rutas:** `/gestion/proveedores/facturas/` · `.../crear/` · `.../<pk>/` · `.../<pk>/editar/`

Al crear una factura recibida:

| Campo | Obligatorio |
|---|---|
| N° de factura | Sí |
| Proveedor | Sí (autocomplete) |
| Fecha de emisión | Sí |
| Fecha de vencimiento | No — si se ingresa crea una CxP automáticamente |
| Proyecto asociado | No (autocomplete) |
| Monto neto | Sí — IVA y total se calculan automáticamente |
| Estado | `Pendiente`, `Pagada`, `Vencida`, `Anulada` |

#### Líneas de detalle (DetalleFacturaRecibida)

La sección **Líneas de detalle** permite desagregar el monto de la factura por concepto. Cada línea contiene:

- **Descripción** del ítem o servicio
- **Cuenta contable** (opcional) — permite imputar el gasto a una cuenta del Plan de Cuentas
- **Monto** parcial

**Cómo agregar una línea:**

1. Haga clic en **Agregar línea**.
2. Se abre un modal. Ingrese descripción, seleccione la cuenta contable (con búsqueda) y el monto.
3. Confirme con **Agregar** o presionando Enter.

**Editar una línea:** use el ícono ✏️ en la fila. Se reabre el modal pre-completado.

**Eliminar una línea:** use el ícono 🗑️. La fila desaparece de la vista y se marcará para borrado al guardar.

> Las líneas se guardan junto con la factura al hacer clic en **Registrar factura** o **Guardar cambios**. No es necesario guardar por separado.

---

## 6. Cuentas por Pagar y Anticipos

### 6.1 Cuentas por Pagar

**Ruta:** `/gestion/proveedores/cxp/`

Se crea automáticamente al registrar una factura recibida con fecha de vencimiento. Funciona igual que CxC pero para pagos salientes. El botón **Pagar** marca la CxP y la factura como `Pagada`.

### 6.2 Anticipos a Proveedores

**Rutas:** `/gestion/proveedores/anticipos/` · `.../crear/`

Registra pagos anticipados a proveedores antes de recibir factura. Campos: proveedor, fecha, monto, descripción, estado (`Pendiente`, `Aplicado`, `Devuelto`), proyecto opcional.

---

## 7. Proyectos y Control de Costos

### 7.1 Proyectos

**Rutas:** `/gestion/proyectos/` · `.../crear/` · `.../<pk>/` · `.../<pk>/editar/`

Cada proyecto registra:

| Campo | Notas |
|---|---|
| Código | Único |
| Nombre | |
| Cliente | Opcional |
| Estado | `Negociación`, `Adjudicado`, `En ejecución`, `Terminado`, `Cancelado` |
| Fechas inicio / término | |
| Monto contrato | Base para cálculo de rentabilidad |
| Imagen | Foto representativa |
| Destacado / Mostrar en web | Controlan la visibilidad en el sitio público |

El **detalle del proyecto** muestra:

- Todos los costos registrados con su total
- Rentabilidad = monto contrato − total costos
- Porcentaje de margen
- Líneas presupuestadas vs. reales

### 7.2 Costos de Proyecto

**Ruta:** `/gestion/proyectos/<pk>/costos/crear/`

Cada costo se clasifica por tipo: `Material`, `Mano de obra`, `Subcontrato`, `Equipo`, `Transporte`, `Otro`. Puede vincularse a:

- Una cuenta del Plan de Cuentas
- Un proveedor
- Una factura recibida (trazabilidad documental)

### 7.3 Presupuesto

**Ruta:** `/gestion/proyectos/<pk>/presupuesto/`

Permite ingresar montos presupuestados por ítem/tipo y compararlos con los costos reales acumulados. La variación (real − presupuestado) se calcula automáticamente.

---

## 8. Recursos Humanos

### 8.1 Trabajadores

**Rutas:** `/gestion/rrhh/` · `.../crear/` · `.../<pk>/` · `.../<pk>/editar/`

Ficha del trabajador: RUT, nombres, cargo, fechas de ingreso/término, sueldo base, AFP, ISAPRE, datos bancarios para pago, estado (`Activo`, `Inactivo`, `Licencia`, `Vacaciones`).

El **detalle del trabajador** muestra los últimos 12 recibos de sueldo, últimos 10 anticipos y últimas 10 entradas del historial laboral.

### 8.2 Remuneraciones

**Rutas:** `/gestion/rrhh/remuneraciones/` · `.../crear/`

Cada liquidación de sueldo registra:

| Componente | Campo |
|---|---|
| Período | Mes y año |
| Haberes | Sueldo base, horas extra, bono |
| Descuentos | AFP, salud, otros descuentos, anticipo descontado |
| Resultado | Sueldo bruto, líquido a pagar |
| Estado | `Borrador`, `Aprobado`, `Pagado` |
| Fecha de pago | Opcional |

### 8.3 Anticipos Laborales

**Rutas:** `/gestion/rrhh/anticipos/` · `.../crear/`

Registra adelantos de sueldo. Estado: `Pendiente` (aún no descontado) o `Descontado` (incluido en una liquidación).

---

## 9. Tesorería y Movimientos Bancarios

### 9.1 Resumen de Tesorería

**Ruta:** `/gestion/tesoreria/`

Muestra todas las cuentas bancarias activas con su saldo actual y los últimos 20 movimientos del sistema.

**Saldo actual** = saldo inicial + Σ ingresos − Σ egresos (calculado desde los movimientos registrados).

### 9.2 Bancos y Cuentas

| Módulo | Rutas |
|---|---|
| Bancos | `/gestion/tesoreria/bancos/` · `.../crear/` |
| Cuentas bancarias | `/gestion/tesoreria/cuentas/` · `.../crear/` · `.../<pk>/editar/` |

Cada cuenta almacena banco, número, tipo (Corriente / Ahorro / Vista / RUT), saldo inicial y estado activo.

### 9.3 Movimientos Bancarios

**Rutas:** `/gestion/tesoreria/movimientos/` · `.../crear/` · `.../<pk>/editar/`

Cada movimiento registra:

| Campo | Notas |
|---|---|
| Cuenta bancaria | |
| Fecha | |
| Tipo | `Ingreso` o `Egreso` |
| Monto | |
| Descripción | |
| Cuenta contable | Opcional — para imputación contable |
| Proyecto | Opcional |
| N° documento | Referencia (boleta, cheque, etc.) |
| Conciliado | Marca de conciliación bancaria |

---

## 10. Plan de Cuentas

**Ruta:** `/gestion/contabilidad/`

El plan de cuentas tiene estructura jerárquica de 4 niveles. Los códigos siguen el patrón `1` → `1.01` → `1.01.01` → `1.01.01.01`.

| Tipo | Descripción |
|---|---|
| `Activo` | Bienes y derechos de la empresa |
| `Pasivo` | Obligaciones |
| `Ingreso` | Ventas y otros ingresos |
| `Costo` | Costos directos de ventas |
| `Gasto` | Gastos operacionales |
| `Socio` | Cuentas de patrimonio / socios |

Operaciones disponibles: crear cuenta, editar, eliminar (si no tiene movimientos asociados).

El flag **Acepta movimientos** indica que la cuenta es de nivel hoja y puede recibir imputaciones directas desde movimientos bancarios, costos de proyectos y detalles de facturas.

---

## 11. Contabilidad y Libro Diario

El módulo de contabilidad implementa **partida doble**: cada operación económica genera un asiento con líneas de Debe y Haber cuya sumatoria debe ser igual.

### 11.1 Configuración Contable

**Ruta:** `/gestion/contabilidad/configuracion/`

> ⚠️ **Este paso es obligatorio antes de usar cualquier función contable.** Sin configuración, los botones de generación automática no producirán asientos.

Asigne una cuenta del Plan de Cuentas a cada concepto fijo:

| Campo | Qué cuenta asignar (ejemplo) |
|---|---|
| **Cuenta CxC** | `1.01.03.01 – Clientes Nacionales` |
| **Cuenta CxP** | `2.01.01.01 – Facturas por Pagar` |
| **IVA Débito Fiscal** | `2.01.02.01 – IVA Débito Fiscal` |
| **IVA Crédito Fiscal** | `1.01.04.01 – IVA Crédito Fiscal` |
| **Ingresos por defecto** | `4.01.01.01 – Ventas` |
| **Costos/Compras por defecto** | `5.01.01.01 – Costo de Ventas` |

Use el buscador para encontrar cada cuenta por código o nombre. Guarde con **Guardar configuración**.

### 11.2 Libro Diario

**Ruta:** `/gestion/contabilidad/diario/`

Lista todos los asientos contables con filtros por tipo, estado y rango de fechas.

Cada asiento puede estar en uno de tres estados:

| Estado | Significado |
|---|---|
| **Borrador** | Generado automáticamente o ingresado manualmente. Editable. No afecta reportes. |
| **Confirmado** | Revisado y aprobado. Solo estos asientos alimentan los reportes contables. |
| **Anulado** | Invalidado. Se conserva el registro histórico pero no afecta reportes. |

#### Crear asiento manual

1. En `/gestion/contabilidad/diario/` haga clic en **Nuevo asiento**.
2. Indique fecha, descripción y tipo.
3. Agregue líneas con **Agregar línea**: seleccione la cuenta, indique si es Debe o Haber y el monto.
4. El pie de página muestra los totales en tiempo real. El campo **Diferencia** debe ser `$ 0` para que el asiento esté cuadrado.
5. Guarde. El asiento queda en *Borrador*.
6. Revíselo y haga clic en **Confirmar** cuando esté correcto.

#### Generar asiento automáticamente

Desde el detalle de una **Factura Emitida** o **Factura Recibida** hay un botón **Generar asiento contable** que crea el asiento en borrador con todas las líneas pre-calculadas. Revíselo y confirme.

Desde la lista de **Movimientos Bancarios**, el ícono <kbd>📒+</kbd> de cada fila genera el asiento del movimiento (requiere que la cuenta bancaria tenga su cuenta contable configurada).

### 11.3 Reportes Contables

Todos los reportes filtran **solo asientos confirmados**.

| Reporte | Ruta | Qué muestra |
|---|---|---|
| **Libro Mayor** | `/gestion/contabilidad/mayor/` | Movimientos de una cuenta con saldo acumulado. Seleccione cuenta y período. |
| **Balance de Comprobación** | `/gestion/contabilidad/balance-comprobacion/` | Debe, Haber y saldo neto por cada cuenta activa. Total Debe = Total Haber como validación. |
| **Balance General** | `/gestion/contabilidad/balance-general/` | Saldos agrupados en Activo / Pasivo / Patrimonio a una fecha de corte. |
| **Estado de Resultados** | `/gestion/contabilidad/estado-resultados/` | Ingresos − (Costos + Gastos) = Utilidad del período. |

---

## 12. Tributario

### 12.1 Registros de Compra y Venta

| Módulo | Ruta | Descripción |
|---|---|---|
| Registro de Compras | `/gestion/tributario/compras/` | Libro de compras generado a partir de facturas recibidas. Filtrable por mes/año. |
| Registro de Ventas | `/gestion/tributario/ventas/` | Libro de ventas generado a partir de facturas emitidas. |

Ambos muestran totales de columna (neto, IVA, total) al pie de cada listado.

### 12.2 Declaración de IVA

**Rutas:** `/gestion/tributario/iva/` · `.../crear/` · `.../<pk>/editar/`

Registra la declaración mensual de IVA:

| Campo | Notas |
|---|---|
| Período (mes / año) | Único por período |
| IVA débito | IVA de ventas |
| IVA crédito | IVA de compras |
| Diferencia | Calculada: `max(débito − crédito, 0)` |
| Estado | `Borrador`, `Presentado`, `Pagado` |
| Fecha de presentación | |

### 12.3 PPM (Pagos Provisionales Mensuales)

**Rutas:** `/gestion/tributario/ppm/` · `.../crear/`

Registra el PPM mensual con base imponible, tasa (por defecto 0,25 %) y monto calculado. Estado: `Pendiente` / `Pagado`.

### 12.4 Formulario F-29

**Rutas:** `/gestion/tributario/f29/` · `.../crear/` · `.../<pk>/editar/`

Consolida en un formulario el pago mensual de obligaciones tributarias:

| Campo | Descripción |
|---|---|
| IVA a pagar | Desde declaración IVA |
| PPM a pagar | Desde registro PPM |
| Retenciones | Honorarios u otras retenciones |
| Total a pagar | `IVA + PPM − Retenciones` |
| Estado | `Pendiente`, `Presentado`, `Pagado` |
| Folio SII | Número de folio del formulario presentado |

---

## 13. Usuarios y Roles

**Rutas:** `/gestion/usuarios/` · `.../crear/` · `.../<pk>/editar/`  
**Perfil propio:** `/gestion/perfil/`

### Roles disponibles

| Rol | Perfil esperado |
|---|---|
| `admin` | Acceso total al sistema |
| `gerente` | Consulta y aprobación de gestión |
| `contador` | Contabilidad, tributario, plan de cuentas |
| `rrhh` | Módulo de recursos humanos |
| `tesorero` | Tesorería y movimientos bancarios |
| `vendedor` | Clientes y facturas emitidas |
| `operador` | Proyectos y costos |
| `solo_lectura` | Consulta sin modificaciones |

> **Nota:** la lógica de permisos por rol está definida pero el control de acceso granular por rol no se aplica automáticamente en las vistas actuales. Todas las vistas requieren únicamente autenticación (`GestionMixin`).

Cada usuario almacena cargo, teléfono y foto de avatar. El nombre mostrado en el topbar proviene del método `nombre_display`.

---

## 14. Sitio Web Público

El sitio público (sin login) se accede desde la raíz del dominio `/`.

| Página | Ruta | Contenido |
|---|---|---|
| Inicio | `/` | Hasta 6 proyectos destacados + hasta 6 servicios activos |
| Proyectos | `/proyectos/` | Portafolio completo, filtrable por categoría |
| Servicios | `/servicios/` | Lista de servicios con ícono e imagen |
| Nosotros | `/nosotros/` | Equipo activo con foto y LinkedIn |
| Contacto | `/contacto/` | Formulario de contacto (guarda `ContactoMensaje`) |

### Gestión del contenido web

El contenido del sitio se controla desde los modelos:

- **`ProyectoPortafolio`**: los proyectos con `mostrar_en_web = True` y `destacado = True` aparecen en el inicio. Puede vincularse a un proyecto interno.
- **`Servicio`**: activos y ordenados por el campo `orden`.
- **`MiembroEquipo`**: activos y ordenados por `orden`.
- **`ContactoMensaje`**: los mensajes recibidos se pueden marcar como `leído` y `respondido` desde el admin de Django (`/admin/`).

> Para que un proyecto interno aparezca en el portafolio, active el flag **Mostrar en web** en el formulario del proyecto.

---

## 15. Relaciones entre módulos

```
Clientes ──────► FacturaEmitida ──────► CuentaPorCobrar
                      │
                      └──► Proyecto ◄──── CostoProyecto ◄── FacturaRecibida
                                                                    │
Proveedores ────► FacturaRecibida ──►CuentaPorPagar          DetalleFacturaRecibida
                      │                                             │
                      └──────────────────────────────────────► PlanCuentas
                                                                    ▲
MovimientoBancario ──────────────────────────────────────────────── │
CostoProyecto ────────────────────────────────────────────────────── │

Trabajador ──────► Remuneracion
           ──────► AnticipoLaboral
           ──────► HistorialLaboral

FacturaEmitida ──► RegistroVenta ──┐
                                    ├──► DeclaracionIVA ──► FormularioF29
FacturaRecibida ► RegistroCompra ──┘
```

### Automatismos clave

| Acción | Efecto automático |
|---|---|
| Crear `FacturaEmitida` con fecha de vencimiento | Se crea una `CuentaPorCobrar` |
| Crear `FacturaRecibida` con fecha de vencimiento | Se crea una `CuentaPorPagar` |
| Pagar una CxC / CxP | Se actualiza el estado de la factura asociada |
| Guardar `FacturaEmitida` o `FacturaRecibida` | IVA = neto × 0.19, Total = neto + IVA |
| Guardar `DeclaracionIVA` | Diferencia = max(débito − crédito, 0) |
| Guardar `FormularioF29` | Total = IVA + PPM − Retenciones |
| Agregar `MovimientoBancario` | Saldo actual de la cuenta se recalcula |
| Generar asiento de `FacturaEmitida` | Asiento borrador DEBE CxC / HABER Ventas + IVA Débito |
| Generar asiento de `FacturaRecibida` | Asiento borrador DEBE Costos + IVA Crédito / HABER CxP |
| Generar asiento de `MovimientoBancario` | Asiento borrador DEBE/HABER Banco ↔ cuenta contrapartida |

---

## 16. Ejemplo: flujo contable completo

Este ejemplo recorre **un mes de operaciones** desde cero, mostrando exactamente qué hacer en el sistema en cada paso.

> **Escenario:** junio 2026.  
> STA emite una factura a un cliente, recibe una factura de un proveedor y registra el cobro bancario al final del mes.

---

### Paso 0 — Configurar las cuentas contables (solo la primera vez)

1. En el menú lateral, haga clic en **Config. Contable** (bajo el grupo *Finanzas*).
2. Asigne cada campo a la cuenta correspondiente en el plan. Ejemplo mínimo:

   | Campo | Cuenta sugerida |
   |---|---|
   | Cuenta CxC | `Clientes Nacionales` |
   | Cuenta CxP | `Facturas por Pagar` |
   | IVA Débito Fiscal | `IVA Débito Fiscal` |
   | IVA Crédito Fiscal | `IVA Crédito Fiscal` |
   | Ingresos por defecto | `Ventas` |
   | Costos por defecto | `Costo de Ventas` |

3. Haga clic en **Guardar configuración**.

> Este paso solo se realiza una vez. Si más adelante cambia de plan de cuentas, vuelva aquí a actualizar.

---

### Paso 1 — Emitir una factura de venta

**Situación:** STA factura $1.000.000 neto al cliente Constructora Rivera por el Proyecto Edificio Norte.

1. Vaya a **Facturas Emitidas → Nueva factura**.
2. Complete:
   - Cliente: `Constructora Rivera`
   - Fecha emisión: `03/06/2026`
   - Fecha vencimiento: `03/07/2026`
   - Monto neto: `1.000.000`
   - Proyecto: `Edificio Norte`
3. En la sección **Líneas de detalle**, agregue:
   - Descripción: `Fabricación e instalación de muebles cocina`
   - Cantidad: `1` · Precio unitario: `1.000.000`
   - Cuenta contable de la línea: `Ventas` (opcional pero recomendado para mayor precisión)
4. Haga clic en **Registrar factura**.

**Resultado automático:**
- IVA calculado: `$190.000` · Total: `$1.190.000`
- Se crea una **CxC** por `$1.190.000` con vencimiento 03/07/2026.

---

### Paso 2 — Generar el asiento de la factura emitida

1. Haga clic en el número de factura para ir a su detalle.
2. En el panel lateral derecho verá el botón **Generar asiento contable**. Haga clic.
3. El sistema crea el asiento `AJ-2026-0001` en estado *Borrador* con las siguientes partidas:

   | Cuenta | Debe | Haber |
   |---|---|---|
   | Clientes Nacionales | $1.190.000 | — |
   | Ventas | — | $1.000.000 |
   | IVA Débito Fiscal | — | $190.000 |
   | **Total** | **$1.190.000** | **$1.190.000** |

4. Revise que el asiento esté cuadrado (el pie de la tabla mostrará ✅ *Asiento cuadrado*).
5. Haga clic en **Confirmar**. El asiento pasa a estado *Confirmado* y ya no es editable.

---

### Paso 3 — Registrar una factura de compra

**Situación:** STA recibe una factura de Proveedor Maderas del Sur por $500.000 neto en materiales.

1. Vaya a **Facturas Recibidas → Nueva factura recibida**.
2. Complete:
   - Proveedor: `Maderas del Sur`
   - Fecha emisión: `05/06/2026`
   - Fecha vencimiento: `05/07/2026`
   - Monto neto: `500.000`
3. En las **Líneas de detalle**, agregue:
   - Descripción: `Tableros melamina 18mm`
   - Cuenta contable: `Costo de Ventas`
   - Monto: `500.000`
4. Haga clic en **Registrar factura**.

**Resultado automático:** se crea una **CxP** por `$595.000`.

---

### Paso 4 — Generar el asiento de la factura recibida

1. Abra el detalle de la factura recibida.
2. Haga clic en **Generar asiento contable**.
3. El sistema crea el asiento `AJ-2026-0002` en *Borrador*:

   | Cuenta | Debe | Haber |
   |---|---|---|
   | Costo de Ventas | $500.000 | — |
   | IVA Crédito Fiscal | $95.000 | — |
   | Facturas por Pagar | — | $595.000 |
   | **Total** | **$595.000** | **$595.000** |

4. Confirme el asiento.

---

### Paso 5 — Registrar el cobro bancario

**Situación:** el 30/06/2026 Constructora Rivera paga $1.190.000 a la cuenta corriente de STA.

1. Primero, asegúrese de que la **cuenta bancaria** tenga asignada su cuenta contable:
   - Vaya a **Tesorería → Cuentas bancarias → Editar** la cuenta corriente.
   - En el campo **Cuenta Contable** seleccione la cuenta del plan que representa esa cuenta bancaria (ej. `Banco Cuenta Corriente`).
   - Guarde.

2. Vaya a **Movimientos Bancarios → Nuevo movimiento**:
   - Cuenta: `Cta. Cte. Banco Chile`
   - Fecha: `30/06/2026`
   - Tipo: `Ingreso`
   - Monto: `1.190.000`
   - Descripción: `Cobro Factura 0001 – Constructora Rivera`
   - Cuenta contable del movimiento: `Clientes Nacionales` (la contrapartida)
   - Documento: `Transferencia electrónica`
3. Guarde el movimiento.

---

### Paso 6 — Generar el asiento del cobro bancario

1. En la lista de **Movimientos Bancarios**, busque el movimiento recién ingresado.
2. Haga clic en el ícono 📒+ de la columna Acciones.
3. El sistema crea el asiento `AJ-2026-0003` en *Borrador*:

   | Cuenta | Debe | Haber |
   |---|---|---|
   | Banco Cuenta Corriente | $1.190.000 | — |
   | Clientes Nacionales | — | $1.190.000 |
   | **Total** | **$1.190.000** | **$1.190.000** |

4. Confirme el asiento.

> Nótese que este asiento cancela la CxC: la cuenta `Clientes Nacionales` ahora tiene un Debe de $1.190.000 (de la venta) y un Haber de $1.190.000 (del cobro), saldo neto = $0.

---

### Paso 7 — Revisar los reportes del mes

Con los tres asientos confirmados, los reportes ya reflejan la realidad del mes:

#### Libro Mayor — cuenta «Ventas»

| Fecha | Asiento | Debe | Haber | Saldo |
|---|---|---|---|---|
| 03/06/2026 | AJ-2026-0001 | — | $1.000.000 | $1.000.000 |

> Saldo acreedor de $1.000.000 en ingresos.

#### Estado de Resultados (junio 2026)

| Concepto | Monto |
|---|---|
| Ingresos (Ventas) | $1.000.000 |
| Costos (Costo de Ventas) | $500.000 |
| **Utilidad bruta** | **$500.000** |

#### Balance de Comprobación

| Cuenta | Debe | Haber | Saldo |
|---|---|---|---|
| Banco Cta. Cte. | $1.190.000 | — | $1.190.000 |
| Clientes Nacionales | $1.190.000 | $1.190.000 | $0 |
| IVA Crédito Fiscal | $95.000 | — | $95.000 |
| Costo de Ventas | $500.000 | — | $500.000 |
| Ventas | — | $1.000.000 | $1.000.000 |
| IVA Débito Fiscal | — | $190.000 | $190.000 |
| Facturas por Pagar | — | $595.000 | $595.000 |
| **Totales** | **$2.975.000** | **$2.975.000** | — |

> ✅ Debe = Haber → el sistema está cuadrado.

---

### Resumen del flujo en una línea

```
Registrar documento → Generar asiento (automático) → Revisar borrador → Confirmar → Reportes
```

### Errores frecuentes

| Problema | Solución |
|---|---|
| El botón «Generar asiento» no aparece o no hace nada | Verifique que **Config. Contable** tenga las 6 cuentas asignadas |
| El movimiento bancario no genera asiento | La **cuenta bancaria** y el **movimiento** deben tener su campo «Cuenta contable» completado |
| El asiento no se puede confirmar | El Debe y el Haber no son iguales — revise los montos de las líneas |
| Una factura ya tiene asiento y se necesita corregir | Anule el asiento actual y genere uno nuevo, o edite el borrador si aún no fue confirmado |

---

*Manual generado automáticamente — STA Muebles y Terminaciones · Junio 2026*
