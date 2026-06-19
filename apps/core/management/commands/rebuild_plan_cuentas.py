from django.core.management.base import BaseCommand
from apps.contabilidad.models import AsientoContable, PlanCuentas

PLAN = [
    # ACTIVOS
    ('ACTIVOS', 'Activos Fijos', 'Maquinarias', 'Banco Escuadrador'),
    ('ACTIVOS', 'Activos Fijos', 'Maquinarias', 'Enchapadora de Cantos'),
    ('ACTIVOS', 'Activos Fijos', 'Maquinarias', 'Tupi de Banco'),
    ('ACTIVOS', 'Activos Fijos', 'Maquinarias', 'Perforadora Multiple'),
    ('ACTIVOS', 'Activos Fijos', 'Maquinarias', 'Taladro de Pedastal'),
    ('ACTIVOS', 'Activos Fijos', 'Vehiculos', 'Camioneta'),
    ('ACTIVOS', 'Activos Fijos', 'Vehiculos', 'Furgoneta'),
    ('ACTIVOS', 'Activos Fijos', 'Bien Raiz', 'Terrenos'),
    ('ACTIVOS', 'Activos Fijos', 'Bien Raiz', 'Departamento'),
    ('ACTIVOS', 'Activos Fijos', 'Bien Raiz', 'Galpon'),
    ('ACTIVOS', 'Activos Fijos', 'Equipos Computacionales', 'Computadores'),
    ('ACTIVOS', 'Activos Fijos', 'Equipos Computacionales', 'Impresoras'),
    ('ACTIVOS', 'Activos Fijos', 'Equipos Computacionales', 'Celulares'),
    ('ACTIVOS', 'Activos Fijos', 'Mobiliario Oficina', 'Sillas de Escritorio'),
    ('ACTIVOS', 'Activos Fijos', 'Mobiliario Oficina', 'Mesa de Juntas'),
    ('ACTIVOS', 'Activos Fijos', 'Mobiliario Oficina', 'Escritorios'),
    ('ACTIVOS', 'Activos Fijos', 'Mobiliario Oficina', 'Estanterias'),
    ('ACTIVOS', 'Activos Corrientes', 'Efectivo y Equivalentes', 'Banco Santander'),
    ('ACTIVOS', 'Activos Corrientes', 'Efectivo y Equivalentes', 'Banco BCI'),
    ('ACTIVOS', 'Activos Corrientes', 'Efectivo y Equivalentes', 'Caja Chica'),
    ('ACTIVOS', 'Activos Corrientes', 'Efectivo y Equivalentes', 'Caja Oficina'),
    ('ACTIVOS', 'Activos Corrientes', 'Efectivo y Equivalentes', 'Inversion / Ahorro'),
    ('ACTIVOS', 'Activos Corrientes', 'Cuentas por Cobrar', 'Clientes Nacionales'),
    ('ACTIVOS', 'Activos Corrientes', 'Anticipo Entregados', 'Anticipo Proveedores'),
    ('ACTIVOS', 'Activos Corrientes', 'Anticipo Entregados', 'Anticipo Sueldos'),
    ('ACTIVOS', 'Activos Corrientes', 'Anticipo Entregados', 'Anticipo Honorarios'),
    ('ACTIVOS', 'Activos Corrientes', 'Impuestos por Recuperar', 'Iva Credito Fiscal'),
    ('ACTIVOS', 'Activos Corrientes', 'Impuestos por Recuperar', 'PPM'),
    # PASIVOS
    ('PASIVOS', 'Pasivos Corrientes', 'Proveedores', 'Facturas por Pagar'),
    ('PASIVOS', 'Pasivos Corrientes', 'Remuneraciones por Pagar', 'Sueldos por Pagar'),
    ('PASIVOS', 'Pasivos Corrientes', 'Obligaciones Previsionales', 'Previred Por Pagar'),
    ('PASIVOS', 'Pasivos Corrientes', 'Provisiones Laborales', 'Vacaciones Por Pagar'),
    ('PASIVOS', 'Pasivos Corrientes', 'Provisiones Laborales', 'Feriado Proporcional'),
    ('PASIVOS', 'Pasivos Corrientes', 'Finiquitos', 'Finiquitos por Pagar'),
    ('PASIVOS', 'Pasivos Corrientes', 'Finiquitos', 'Indemnizaciones por Pagar'),
    ('PASIVOS', 'Pasivos Corrientes', 'Impuestos por Pagar', 'Impuestos por Pagar'),
    ('PASIVOS', 'Pasivos Corrientes', 'Impuestos por Pagar', 'Iva Debito Fiscal'),
    ('PASIVOS', 'Pasivos Corrientes', 'Impuestos por Pagar', 'Retenciones Honorarios'),
    ('PASIVOS', 'Pasivos Corrientes', 'Impuestos por Pagar', 'Impuestos Unicos Trabajadores'),
    ('PASIVOS', 'Pasivos Corrientes', 'Prestamos Bancarios', 'Credito Bancario'),
    ('PASIVOS', 'Pasivos Corrientes', 'Prestamos Externos', 'Prestamo a Terceros'),
    ('PASIVOS', 'Pasivos Corrientes', 'Financiamiento Relacionado', 'Mutuo Socio'),
    ('PASIVOS', 'Pasivos Corrientes', 'Financiamiento Relacionado', 'Prestamo Accionista'),
    ('PASIVOS', 'Pasivos Corrientes', 'Financiamiento Relacionado', 'Prestamo Empresa Relacionada'),
    ('PASIVOS', 'Pasivos Corrientes', 'Anticipo Clientes', 'Anticipo Obra'),
    ('PASIVOS', 'Pasivos Corrientes', 'Anticipo Clientes', 'Garantia Retenidas'),
    ('PASIVOS', 'Pasivos No Corrientes', 'Creditos', 'Credito Hipotecario'),
    ('PASIVOS', 'Pasivos No Corrientes', 'Creditos', 'Arrendamientos Financieros'),
    # PATRIMONIO
    ('PATRIMONIO', 'Capital', 'Capital Social', 'Capital Socios'),
    ('PATRIMONIO', 'Resultados', 'Resultados Acumulados', 'Utilidades Retenidas'),
    ('PATRIMONIO', 'Resultados', 'Resultado del Ejercicio', 'Utilidad o Perdida'),
    ('PATRIMONIO', 'Reservas', 'Reserva Legal', 'Reserva Legal 10%'),
    # INGRESOS
    ('INGRESOS', 'Ventas', 'Obras Publicas', 'Cesfam'),
    ('INGRESOS', 'Ventas', 'Obras Publicas', 'Poder Judicial'),
    ('INGRESOS', 'Ventas', 'Clinicas', 'Clinicas'),
    ('INGRESOS', 'Ventas', 'Constructoras', 'Constructora X'),
    ('INGRESOS', 'Ventas', 'Constructoras', 'Constructora Y'),
    ('INGRESOS', 'Ventas', 'Particulares', 'Cliente Particular'),
    ('INGRESOS', 'Otros Ingresos', 'Recuperaciones', 'Seguros'),
    ('INGRESOS', 'Otros Ingresos', 'Intereses', 'Bancarios'),
    ('INGRESOS', 'Otros Ingresos', 'Otros Ingresos', 'Otros'),
    # COSTOS OPERACIONALES
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Martillos'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Destornilladores'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Alicates'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Llaves'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Formones'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Nivel de Burbuja'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Nivel de Laser'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Prensas'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Cartonero'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Espátulas'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Limas'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Mazo de Goma'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Menores', 'Palas'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Taladros'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Atornilladores'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Esmeriles'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Caladoras'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Sierras Circulares'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Fresadoras'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Rotomartillos'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Lijadoras'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Cepillo Electrico'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Compresor'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Herramientas Electricas', 'Soldadora'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Brocas'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Hojas de Sierra'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Discos de Corte'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Lijas'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Tornillos'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Barniz'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Colafria'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Adhesivos de Contacto'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Puntas de Atornillador'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Pinturas'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Consumibles de Herramientas', 'Bolsas y Paños'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Elementos de Medición', 'Huincha de medir'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Elementos de Medición', 'Regla'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Elementos de Medición', 'Cuerda'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Elementos de Medición', 'Escalimetro'),
    ('COSTOS OPERACIONALES', 'Herramientas Op', 'Elementos de Medición', 'Escuadras'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Tableros', 'Melamina'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Tableros', 'MDF'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Tableros', 'Terciados y Maderas'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Revestimientos', 'Corian'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Revestimientos', 'Canto PVC'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Cubiertas', 'Granito'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Cubiertas', 'Marmol'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Metales', 'Fierros Tubulares'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Vidrios', 'Vidrio'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Adhesivos', 'Silicona'),
    ('COSTOS OPERACIONALES', 'Materiales e Insumos', 'Adhesivos', 'Espuma Expansiva'),
    ('COSTOS OPERACIONALES', 'Herrajes', 'Movimiento', 'Bisagras'),
    ('COSTOS OPERACIONALES', 'Herrajes', 'Movimiento', 'Correderas'),
    ('COSTOS OPERACIONALES', 'Herrajes', 'Seguridad', 'Cerraduras'),
    ('COSTOS OPERACIONALES', 'Herrajes', 'Terminaciones', 'Tiradores'),
    ('COSTOS OPERACIONALES', 'Herrajes', 'Fijaciones', 'Escuadras'),
    ('COSTOS OPERACIONALES', 'Herrajes', 'Fijaciones', 'Pernos Confirmat'),
    ('COSTOS OPERACIONALES', 'Herrajes', 'Fijaciones', 'Tarugos'),
    ('COSTOS OPERACIONALES', 'Herrajes', 'Fijaciones', 'Pernos de Anclaje'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Manual', 'Guantes Latex'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Manual', 'Guantes Cabritilla'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Manual', 'Guantes Anticorte'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Manual', 'Mangas de Proteccion Soldador'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Visual', 'Lentes de Seguridad'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Visual', 'Antiparras de Sello Hermetico'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Visual', 'Mascara de Soldar'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Visual', 'Liquidos o estacion de Lavado Ocular'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Visual', 'Paños y Liquidos Antiempañantes'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Auditiva', 'Orejeras'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Auditiva', 'Tapones Auditivos'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Auditiva', 'Almohadillas Rptos'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Respiratoria', 'Mascarillas'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Respiratoria', 'Filtros Mixtos'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Craneal', 'Cascos'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Craneal', 'Barbiquejos'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Craneal', 'Bandas Antisudorales'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Craneal', 'Porta Lamparas'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Corporal', 'Chalecos Reflectantes'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Corporal', 'Overoles de Trabajo'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Corporal', 'Camisas o Poleras de Trabajo'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Corporal', 'Pechera'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Corporal', 'Faja Lumbar'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion Corporal', 'Zapato de Seguridad'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion de Altura', 'Arnes de Seguridad'),
    ('COSTOS OPERACIONALES', 'Elementos Proteccion Personal Op', 'Proteccion de Altura', 'Linea de Vida'),
    ('COSTOS OPERACIONALES', 'Combustibles Op', 'Vehiculos Livianos', 'Gasolina'),
    ('COSTOS OPERACIONALES', 'Combustibles Op', 'Vehiculos Livianos', 'Diesel'),
    ('COSTOS OPERACIONALES', 'Combustibles Op', 'Camiones', 'Diesel'),
    ('COSTOS OPERACIONALES', 'Combustibles Op', 'Maquinarias', 'Combustible Industrial'),
    ('COSTOS OPERACIONALES', 'Lubricantes Op', 'Maquinarias', 'Aceites'),
    ('COSTOS OPERACIONALES', 'Fletes Op', 'Transporte Materiales', 'Traslado Materiales'),
    ('COSTOS OPERACIONALES', 'Mantencion y Reparaciones Op', 'Vehiculos', 'Camioneta'),
    ('COSTOS OPERACIONALES', 'Mantencion y Reparaciones Op', 'Vehiculos', 'Furgoneta'),
    ('COSTOS OPERACIONALES', 'Mantencion y Reparaciones Op', 'Maquinarias', 'Banco Escuadrador'),
    ('COSTOS OPERACIONALES', 'Mantencion y Reparaciones Op', 'Maquinarias', 'Enchapadora de Cantos'),
    ('COSTOS OPERACIONALES', 'Mantencion y Reparaciones Op', 'Maquinarias', 'Tupi de Banco'),
    ('COSTOS OPERACIONALES', 'Mantencion y Reparaciones Op', 'Maquinarias', 'Perforadora Multiple'),
    ('COSTOS OPERACIONALES', 'Mantencion y Reparaciones Op', 'Maquinarias', 'Taladro de Pedastal'),
    ('COSTOS OPERACIONALES', 'Arriendos Op', 'Infraestructura', 'Galpon / Fabrica'),
    ('COSTOS OPERACIONALES', 'Arriendos Op', 'Infraestructura', 'Oficina'),
    ('COSTOS OPERACIONALES', 'Arriendos Op', 'Equipos Op', 'Maquinaria'),
    ('COSTOS OPERACIONALES', 'Arriendos Op', 'Equipos Op', 'Herramientas'),
    ('COSTOS OPERACIONALES', 'Mano De Obra Op', 'Remuneraciones Op', 'Sueldos Produccion'),
    ('COSTOS OPERACIONALES', 'Mano De Obra Op', 'Remuneraciones Op', 'Gratificaciones'),
    ('COSTOS OPERACIONALES', 'Mano De Obra Op', 'Remuneraciones Op', 'Horas Extras'),
    ('COSTOS OPERACIONALES', 'Mano De Obra Op', 'Remuneraciones Op', 'Bonos Produccion'),
    ('COSTOS OPERACIONALES', 'Mano De Obra Op', 'Terminacion Laboral', 'Indemnizaciones'),
    ('COSTOS OPERACIONALES', 'Mano De Obra Op', 'Terminacion Laboral', 'Feriado Proporcional'),
    ('COSTOS OPERACIONALES', 'Servicios Op', 'Soldadura', 'Externo'),
    ('COSTOS OPERACIONALES', 'Servicios Op', 'Transporte Op', 'Externo'),
    ('COSTOS OPERACIONALES', 'Servicios Op', 'Instalaciones', 'Externo'),
    ('COSTOS OPERACIONALES', 'Servicios Op', 'Vidrieria', 'Externo'),
    ('COSTOS OPERACIONALES', 'Servicios Op', 'Serv Asesorias Op', 'Externo'),
    ('COSTOS OPERACIONALES', 'Servicios Basicos Op', 'Electricidad', 'Luz Taller'),
    ('COSTOS OPERACIONALES', 'Servicios Basicos Op', 'Agua', 'Agua Taller'),
    ('COSTOS OPERACIONALES', 'Servicios Basicos Op', 'Gas', 'Calefaccion Taller'),
    ('COSTOS OPERACIONALES', 'Seguridad Op', 'CCTV', 'Camaras Taller'),
    ('COSTOS OPERACIONALES', 'Alimentacion Op', 'Colaciones Personal', 'Alimentacion'),
    ('COSTOS OPERACIONALES', 'Traslado Op', 'Peajes Op', 'Peajes / TAG'),
    ('COSTOS OPERACIONALES', 'Traslado Op', 'Estacionamientos', 'Estacionamientos'),
    ('COSTOS OPERACIONALES', 'Vehiculos Op', 'Documentacion Vehicular', 'Patente Vehiculo'),
    ('COSTOS OPERACIONALES', 'Vehiculos Op', 'Documentacion Vehicular', 'Permiso Circulacion'),
    ('COSTOS OPERACIONALES', 'Vehiculos Op', 'Documentacion Vehicular', 'Revision Tecnica'),
    ('COSTOS OPERACIONALES', 'Vehiculos Op', 'Documentacion Vehicular', 'Soap'),
    ('COSTOS OPERACIONALES', 'Vehiculos Op', 'Rep y Mant Vehicular', 'Reparaciones'),
    # GASTOS ADMINISTRATIVOS
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Contabilidad', 'Honorarios Contables'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Legal', 'Abogado'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Legal', 'Notaria'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Financiera', 'Asesoria Financiera'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Arquitectura', 'Arquitecto'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Informatica', 'Desarrollo de Software'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Informatica', 'Hosting'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Informatica', 'Dominio Web'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Informatica', 'Soporte Tecnico'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Recursos Humanos', 'Reclutamiento'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Recursos Humanos', 'Capacitacion'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Prevencion de Riesgos', 'Asesoria PRP'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Profesionales', 'Prevencion de Riesgos', 'Documentacion PRP'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Bancarios', 'Comisiones Bancarias', 'Mantencion Cta Cte'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Bancarios', 'Comisiones Bancarias', 'Transferencias'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Bancarios', 'Comisiones Bancarias', 'Comision POS / Transbank'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Bancarios', 'Financiamiento', 'Intereses Linea de Credito'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Bancarios', 'Financiamiento', 'Intereses Prestamos'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Tributarios', 'Municipales', 'Patente Municipal'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Tributarios', 'Municipales', 'Derechos Municipales'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Tributarios', 'Notariales', 'Notaria'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Tributarios', 'Conservador', 'Conservador Bienes Raices'),
    ('GASTOS ADMINISTRATIVOS', 'Gastos Tributarios', 'Certificaciones', 'Certificados'),
    ('GASTOS ADMINISTRATIVOS', 'Oficina', 'Papeleria', 'Papel'),
    ('GASTOS ADMINISTRATIVOS', 'Oficina', 'Papeleria', 'Carpetas'),
    ('GASTOS ADMINISTRATIVOS', 'Oficina', 'Papeleria', 'Archivadores'),
    ('GASTOS ADMINISTRATIVOS', 'Oficina', 'Impresión', 'Toner'),
    ('GASTOS ADMINISTRATIVOS', 'Oficina', 'Impresión', 'Tinta'),
    ('GASTOS ADMINISTRATIVOS', 'Oficina', 'Articulos de Escritorio', 'Lapices'),
    ('GASTOS ADMINISTRATIVOS', 'Oficina', 'Articulos de Escritorio', 'Calculadoras'),
    ('GASTOS ADMINISTRATIVOS', 'Comunicaciones', 'Telefonia', 'Telefono Movil'),
    ('GASTOS ADMINISTRATIVOS', 'Comunicaciones', 'Telefonia', 'Telefonia Fija'),
    ('GASTOS ADMINISTRATIVOS', 'Comunicaciones', 'Internet', 'Internet Oficina'),
    ('GASTOS ADMINISTRATIVOS', 'Comunicaciones', 'Web', 'Hosting'),
    ('GASTOS ADMINISTRATIVOS', 'Comunicaciones', 'Software', 'Licencias Software'),
    ('GASTOS ADMINISTRATIVOS', 'Seguros', 'Vehiculos', 'Seguro Camioneta'),
    ('GASTOS ADMINISTRATIVOS', 'Seguros', 'Vehiculos', 'Seguro Furgon'),
    ('GASTOS ADMINISTRATIVOS', 'Seguros', 'Infraestructura', 'Seguro Galpon'),
    ('GASTOS ADMINISTRATIVOS', 'Seguros', 'Equipos', 'Seguro Maquinarias'),
    ('GASTOS ADMINISTRATIVOS', 'Seguros', 'Responsabilidad Civil', 'RC Empresa'),
    ('GASTOS ADMINISTRATIVOS', 'Recursos Humanos', 'Bienestar', 'Aguinaldos'),
    ('GASTOS ADMINISTRATIVOS', 'Recursos Humanos', 'Bienestar', 'Celebraciones'),
    ('GASTOS ADMINISTRATIVOS', 'Recursos Humanos', 'Capacitacion', 'Cursos'),
    ('GASTOS ADMINISTRATIVOS', 'Recursos Humanos', 'Capacitacion', 'Certificaciones'),
    ('GASTOS ADMINISTRATIVOS', 'Recursos Humanos', 'Remuneraciones Adm', 'Sueldos Administracion'),
    ('GASTOS ADMINISTRATIVOS', 'Recursos Humanos', 'Remuneraciones Adm', 'Gratificaciones'),
    ('GASTOS ADMINISTRATIVOS', 'Recursos Humanos', 'Remuneraciones Adm', 'Bonos Responsabilidad'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Basicos', 'Electricidad', 'Luz Oficina'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Basicos', 'Agua', 'Agua Oficina'),
    ('GASTOS ADMINISTRATIVOS', 'Servicios Basicos', 'Gas', 'Calefaccion Oficina'),
    ('GASTOS ADMINISTRATIVOS', 'Seguridad', 'CCTV', 'Cámaras'),
    # SOCIO GERENCIA
    ('SOCIO GERENCIA', 'Retiros', 'Socio', 'Retiros Personales'),
    ('SOCIO GERENCIA', 'Gastos Personales', 'Alimentacion', 'Personal'),
    ('SOCIO GERENCIA', 'Gastos Personales', 'Combustible', 'Personal'),
    ('SOCIO GERENCIA', 'Gastos Personales', 'Hogar', 'Personal'),
    ('SOCIO GERENCIA', 'Gastos Personales', 'Otros', 'Personal'),
]

TIPO_MAP = {
    "ACTIVOS": "activo",
    "PASIVOS": "pasivo",
    "INGRESOS": "ingreso",
    "COSTOS OPERACIONALES": "costo",
    "GASTOS ADMINISTRATIVOS": "gasto",
    "SOCIO GERENCIA": "socio",
    "PATRIMONIO": "patrimonio",
}


class Command(BaseCommand):
    help = "Elimina todo el plan de cuentas y lo recrea desde cero con la misma lógica de la migración inicial"

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma la eliminación y recreación del plan de cuentas',
        )
        parser.add_argument(
            '--incluyendo-asientos',
            action='store_true',
            help='Elimina también todos los asientos contables (y sus líneas) antes de reconstruir el plan',
        )

    def handle(self, *args, **options):
        if not options['confirmar']:
            self.stdout.write(self.style.WARNING(
                'Este comando eliminará TODAS las cuentas y las recreará.\n'
                'Ejecuta con --confirmar para proceder.'
            ))
            return

        # Verificar si hay asientos que bloquearían la eliminación
        asientos_count = AsientoContable.objects.count()
        if asientos_count > 0 and not options['incluyendo_asientos']:
            self.stdout.write(self.style.ERROR(
                f'Existen {asientos_count} asientos contables con líneas referenciando cuentas.\n'
                'Agrega --incluyendo-asientos para eliminarlos también (acción irreversible).'
            ))
            return

        if options['incluyendo_asientos'] and asientos_count > 0:
            self.stdout.write(self.style.WARNING(f'Eliminando {asientos_count} asientos contables...'))
            AsientoContable.objects.all().delete()
            self.stdout.write(self.style.WARNING('  Asientos eliminados.'))

        self.stdout.write('Eliminando plan de cuentas existente...')
        total_deleted = 0
        for nivel in (4, 3, 2, 1):
            deleted, _ = PlanCuentas.objects.filter(nivel=nivel).delete()
            total_deleted += deleted
        self.stdout.write(self.style.WARNING(f'  {total_deleted} cuentas eliminadas.'))

        self.stdout.write('Construyendo árbol...')
        tree = {}
        for l1, l2, l3, l4 in PLAN:
            tree.setdefault(l1, {})
            tree[l1].setdefault(l2, {})
            tree[l1][l2].setdefault(l3, [])
            if l4 not in tree[l1][l2][l3]:
                tree[l1][l2][l3].append(l4)

        total = 0
        for l1_idx, (l1_name, l2s) in enumerate(tree.items(), start=1):
            tipo = TIPO_MAP[l1_name]
            l1_code = str(l1_idx)
            l1_obj = PlanCuentas.objects.create(
                codigo=l1_code,
                nombre=l1_name,
                tipo=tipo,
                nivel=1,
                parent=None,
                activa=True,
                acepta_movimientos=False,
            )
            total += 1

            for l2_idx, (l2_name, l3s) in enumerate(l2s.items(), start=1):
                l2_code = f"{l1_code}.{l2_idx:02d}"
                l2_obj = PlanCuentas.objects.create(
                    codigo=l2_code,
                    nombre=l2_name,
                    tipo=tipo,
                    nivel=2,
                    parent=l1_obj,
                    activa=True,
                    acepta_movimientos=False,
                )
                total += 1

                for l3_idx, (l3_name, l4s) in enumerate(l3s.items(), start=1):
                    l3_code = f"{l2_code}.{l3_idx:02d}"
                    l3_obj = PlanCuentas.objects.create(
                        codigo=l3_code,
                        nombre=l3_name,
                        tipo=tipo,
                        nivel=3,
                        parent=l2_obj,
                        activa=True,
                        acepta_movimientos=False,
                    )
                    total += 1

                    for l4_idx, l4_name in enumerate(l4s, start=1):
                        l4_code = f"{l3_code}.{l4_idx:02d}"
                        PlanCuentas.objects.create(
                            codigo=l4_code,
                            nombre=l4_name,
                            tipo=tipo,
                            nivel=4,
                            parent=l3_obj,
                            activa=True,
                            acepta_movimientos=True,
                        )
                        total += 1

        self.stdout.write(self.style.SUCCESS(f'Plan de cuentas reconstruido: {total} cuentas creadas.'))
