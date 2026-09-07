# ECOMMER — Conocimiento para Vendedores

---

## 1. Introducción

### ¿Qué es ECOMMER?

ECOMMER es una plataforma de comercio electrónico tipo **marketplace multi-vendedor** operada por **Ecommer SAS** (NIT: 902008723), con sede en Popayán, Cauca, Colombia (Carrera 2a 3N 23, Antiguo Liceo). La plataforma conecta a microempresarios y fabricantes colombianos con compradores, ofreciendo una experiencia de venta y compra digital sin necesidad de conocimientos técnicos.

### Objetivo de la plataforma

Empoderar a microempresarios colombianos con tecnología de comercio electrónico accesible, integrada y escalable, permitiéndoles vender en línea con el mismo poder que las grandes marcas. El lema operativo es: *"Take Colombian talent to every corner of the planet."*

### Tipos de usuarios

1. **Comprador (Buyer):** Navega el marketplace, busca productos, agrega al carrito, paga y recibe pedidos. El registro y las compras son gratuitos. Solo paga el costo de envío cuando aplica.
2. **Vendedor (Seller):** Crea y administra su tienda dentro del marketplace. Gestiona sus productos, inventario, pedidos y recibe pagos a través de Wompi. Solo ve y gestiona lo que pertenece a su tienda. **No tiene acceso a la configuración global de la plataforma ni a otras tiendas.**
3. **SimetrIA:** Agente de IA propietario de ECOMMER que atiende compradores 24/7 vía WhatsApp, Instagram, Facebook y chat web, sin sacar al comprador del chat. Disponible en planes Tienda y Omnichannel.

### Conceptos principales

| Concepto | Definición |
|---|---|
| **Tienda (Store)** | Entidad que representa el negocio de un vendedor dentro del marketplace. Tiene slug único, logo, descripción, y puede listar productos. |
| **Vendedor (Seller)** | Persona o empresa dueña de una tienda. Se registra con email o Google. |
| **Producto (Product)** | Ítem a la venta con nombre, descripción, precio, imágenes, categorías y variantes. |
| **Variante (ProductVariant)** | Versión específica de un producto (ej: color, talla, tipo de cable). Tiene su propio SKU, precio y stock. |
| **Colección (Collection)** | Agrupación de productos. Puede ser una colección raíz (ej: "Electrónica") o una subcolección (ej: "Audio", "TV y Video"). |
| **Facet (Faceta)** | Atributo de filtrado para productos (ej: Color, Tipo de alimento). Los valores de faceta permiten filtrar en búsquedas. |
| **Pedido (Order)** | Transacción de compra. Pasa por múltiples estados desde "Recibido" hasta "Entregado". |
| **Wompi** | Pasarela de pagos de Bancolombia. Procesa tarjetas de crédito/débito, PSE, Nequi, Daviplata y corresponsales bancarios. |
| **MESSENGER** | Empresa de mensajería local en Popayán para entregas dentro de la ciudad. |
| **Envia.com** | Plataforma logística para envíos nacionales que integra múltiples transportadoras. |
| **DIAN** | Autoridad tributaria colombiana. La facturación electrónica se emite conforme a la Resolución 0227/2025. |
| **SimetrIA** | Agente de IA integrado que atiende consultas de compradores, busca productos y gestiona soporte. |
| **Plan / Suscripción** | Nivel de servicio del vendedor: Free, Store, u Omnichannel. Define límites de productos, variantes y funcionalidades. |

---

## 2. Arquitectura General

### Módulos

Basado en la introspección del schema GraphQL de Vendure, los módulos observados son:

| Módulo | Descripción |
|---|---|---|
| **Mi Tienda** | Perfil, configuración, plan y suscripción del vendedor |
| **Catálogo** | Products, ProductVariants, Collections, Facets, ProductOptions — gestión de productos propios |
| **Pedidos** | Orders, Fulfillments, Payments, Refunds — pedidos de mi tienda |
| **Clientes** | Customers, Addresses — clientes que compraron en mi tienda |
| **Assets** | Gestión de imágenes y archivos (S3: `ecommer-assets`) |
| **Envíos** | ShippingMethods — configurado automáticamente por tienda (MESSENGER) |
| **Pagos** | Wompi — integrado, el vendedor no lo configura |
| **Impuestos** | TaxCategories predefinidas — el vendedor asigna la categoría al producto |
| **Facturación** | Facturación electrónica DIAN (planes Tienda y Omnichannel) |
| **Reportes** | SalesReports, Analytics de mi tienda |
| **Reviews** | ProductReview — reseñas que dejan los compradores en mis productos |
| **Google Sheets** | Importación de productos desde Google Sheets |

### Relaciones

```
Seller    (1) ──< (N) Store
Store     (1) ──< (N) Product
Product   (1) ──< (N) ProductVariant
Product   (N) >──< (N) Collection
Product   (N) >──< (N) FacetValue
Customer  (1) ──< (N) Order
Order     (1) ──< (N) OrderLine ──> ProductVariant
Order     (1) ──< (N) Payment
Order     (1) ──< (N) Fulfillment
Customer  (1) ──< (N) CustomerSubscription ──> Plan
```

### Flujo general

1. **Vendedor** se registra con Google o email en `admin.ecommer.shop`.
2. Crea una **tienda** (Store) y la configura.
3. Crea **productos** con variantes, imágenes, precios y stock.
4. Productos se publican en el **marketplace** (`ecommer.shop`).
5. **Comprador** navega, busca y filtra productos.
6. Agrega al **carrito** y procede al **checkout**.
7. Pago procesado por **Wompi**.
8. Pedido se crea, notifica al vendedor y al sistema logístico.
9. Envío local por **MESSENGER** o nacional por **Envia.com**.
10. Comprador recibe y puede dejar **review**.

---

## 3. Primeros pasos

### ¿Cómo se crea una tienda?

**Requisitos observados:**
- Correo electrónico válido (único requisito obligatorio para empezar).
- Cuenta de Google (opcional, para registro rápido).

**Campos observados en el registro de vendedor:**

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| Email | String | Sí | Usado como identificador |
| Nombre del negocio | String | No observado en detalle | Ejemplo: "Don Julio Store" |
| Categoría del negocio | Selección | No observado en detalle | Ejemplo: "Food" |
| Ciudad | Selección/texto | No observado en detalle | Ejemplo: "Popayán, Cauca" |

**Configuración inicial (observada en el schema):**
- **Dominio:** No observado como campo explícito en el registro inicial. Las tiendas reciben un slug único que determina su URL (`ecommer.shop/store/{slug}`).
- **Moneda:** Peso colombiano (COP). Observado en precios de productos.
- **Idioma:** Español (es) e Inglés (en). Soporte i18n con URLs por locale (`/es/`, `/en/`).
- **País:** Colombia (CO). La plataforma está enfocada en el mercado colombiano.
- **Estado inicial de la tienda:** Al crearse, el vendedor puede empezar a listar productos inmediatamente en el plan Free. Estado "Active store" observado en la landing de sellers.

**Planes disponibles** (verificado vía API `allPlans`):

| Plan | Precio COP | Max Products | Max Variations | AI Access | Facturación Electrónica |
|---|---|---|---|---|---|
| **Free** | $0 / siempre | 15 | 250 | No | No |
| **Tienda** | $29,900 / mes | 500 | 5,000 | Sí | Sí |
| **Omnichannel** | $99,900 / mes | 1,500 | 15,000 | Sí | Sí |

**Features por plan** (verificado vía API `allPlans.planFeatures`):

| Feature | Code | Type | Free | Tienda | Omnichannel |
|---|---|---|---|---|---|
| Max Products | `max_products` | numeric | 15 | 500 | 1,500 |
| Max Variations | `max_variations` | numeric | 250 | 5,000 | 15,000 |
| AI Access (SimetrIA) | `ai_access` | boolean | false | true | true |
| Electronic Billing (DIAN) | `electronic_billing` | boolean | false | true | true |

Los límites se validan en tiempo real mediante las queries `checkProductLimit`, `checkVariationLimit` y `checkFeatureAccess`.

### ¿Cómo acceder al panel de vendedor?

- URL: `https://admin.ecommer.shop/dashboard/login`
- Métodos de autenticación: **Google OAuth** (iniciar sesión con Google) o email/contraseña.
- La plataforma es una **SPA (Single Page Application)** construida con Next.js.

### ¿Cómo cambiar entre tiendas?

**No observado** en detalle. El schema sugiere que un Seller puede tener múltiples Stores, y el panel del vendedor probablemente ofrece un selector.

### ¿Cómo administrar múltiples tiendas?

**No observado** en detalle. La plataforma soporta múltiples tiendas a través del modelo Seller → Store. La API GraphQL expone tipos `Seller`, `Store`, `StoreList`, `StoreSearchResult`, `StoreFilterInput` y `StoreSortParameter`.

---

## 4. Configuración inicial

### Configuración general

El vendedor configura su tienda desde el panel. Los ajustes se guardan por tienda (`SettingsStore`).

### Moneda

- Moneda por defecto: **Peso colombiano (COP)**.
- Símbolo: `$`.
- El tipo `CurrencyCode` está presente en el schema.
- Precios observados en COP: desde $11,900 hasta $154,700.

### Impuestos

**Categorías de impuestos** (el vendedor elige una al crear el producto):

| ID | Nombre | Productos que la usan |
|---|---|---|
| 1 | **Standard Tax** | champiñones Orellana, NARAYANA, Amigurumi, Collar Búho mostacilla, Tope de puerta, Café orgánico, Panela orgánica, Árbol de la vida, Separador de libros |
| 2 | **Reduced Tax** | Stewart Calculo 1 |
| 3 | **Zero Tax** | El Camino de los Reyes |

- **No observado** el valor porcentual específico de cada categoría (ej: IVA 19%, reducido 5%, exento 0%). La estructura de TaxRates por zona existe pero los valores no son expuestos en la Shop API pública.
- Los precios en la API vienen en **centavos de COP** (ej: `price: 5000000` = $50,000.00 COP).

### Métodos de pago

**Pasarela: Wompi (Bancolombia)**

Métodos de pago disponibles para compradores:

| Método | Tipo |
|---|---|
| Tarjetas de crédito | Visa, Mastercard, American Express |
| Tarjetas débito | Vía PSE |
| PSE | Transferencia desde cualquier banco colombiano |
| Nequi | Billetera digital |
| Daviplata | Billetera digital |
| Bancolombia Button | Botón de pago directo Bancolombia |
| Corresponsales bancarios | Pago en efectivo en puntos físicos |

- Wompi tiene certificación **PCI-DSS**.
- Comisión de Wompi: **7.9% por transacción** (cubre tarjetas de crédito, PSE y corresponsales bancarios).
- El vendedor recibe el dinero cada **15 días**.
- Si el vendedor usa Nequi, Bancolombia o banco con clave BRE-B registrada, no hay costos adicionales de transferencia.
- La API de Wompi monitorea pagos 24/7. El dinero solo puede retirarse con segunda clave.
- En caso de reclamos por venta de producto físico, el vendedor tiene **7 días** para demostrar la entrega.

### Métodos de envío

Todos los envíos usan el proveedor **"Domicilio Messenger Domis"** (MESSENGER) con costo calculado automáticamente. Al crear la tienda, el sistema genera automáticamente la configuración de envío.

**Envíos locales (Popayán):**

| Operador | Descripción |
|---|---|
| **MESSENGER (Domis)** | Alianza directa. Al recibir un pedido, el sistema notifica automáticamente a MESSENGER para recoger el paquete en la ubicación del vendedor y entregarlo al comprador. El costo de envío lo asume el comprador y se calcula por distancia. Acceso a más de 15,000 entregas mensuales en Popayán. |

**Envíos nacionales:**

| Operador | Descripción |
|---|---|
| **Envia.com** | Plataforma tecnológica que integra múltiples transportadoras nacionales (incluyendo Servientrega). Calcula tarifas, genera guías, rastrea paquetes. |

### Tipos de autenticación

| Tipo | Descripción |
|---|---|
| Google OAuth | Inicio de sesión con cuenta Google (método principal para vendedores) |
| Email + contraseña | Registro tradicional con correo electrónico |

### Roles y visibilidad

El vendedor solo ve y gestiona **su propia tienda**. No tiene acceso a:
- Otras tiendas del marketplace
- Configuración global de la plataforma
- Gestión de otros vendedores
- Promociones globales

Las queries `checkProductLimit`, `checkVariationLimit` y `checkFeatureAccess` validan en tiempo real si el vendedor está dentro de los límites de su plan.

---

## 5. Gestión del catálogo

### Productos

**Total de productos en el marketplace:** 17 (verificado vía `products.totalItems`).

**Campos de un producto (verificado con datos reales de la API):**

| Campo | Tipo | Ejemplo real |
|---|---|---|
| id | ID | `"256"` |
| name | String | `"Stewart Calculo 1"` |
| slug | String | `"stewart-calculo-1-2"` |
| description | HTML | `<p>libro de calculo</p>` |
| createdAt | DateTime | `"2026-06-12T20:34:42.091Z"` |
| updatedAt | DateTime | `"2026-06-12T20:35:40.481Z"` |
| variants | ProductVariant[] | Ver sección Variantes |
| optionGroups | ProductOptionGroup[] | Grupos como "Cable" |
| facetValues | FacetValue[] | `[{facet: "Categoria", value: "Libros"}]` |
| collections | Collection[] | `[{name: "Libros", slug: "libros"}]` |
| assets | Asset[] | Imágenes con `source` y `preview` (S3) |

**Precios:** Se almacenan en **centavos de COP** en la API. Ejemplos:
- Stewart Calculo 1: `5000000` = $50,000 COP (mostrado como $52,500 en marketplace)
- champiñones Orellana: `1200000` = $12,000 COP (mostrado como $14,280 en marketplace)
- Collar Búho: `13000000` = $130,000 COP (mostrado como $154,700 en marketplace)

La diferencia entre API y marketplace sugiere un markup o cálculo de impuestos sobre el precio base.

**Niveles de stock observados:**
- `IN_STOCK` — Disponible
- `LOW_STOCK` — Stock bajo
- `OUT_OF_STOCK` — Agotado (no observado pero inferido del schema)

**Productos existentes en el marketplace** (17 totales):

| ID | Nombre | Tienda (slug) | Precio API | Categoría |
|---|---|---|---|---|
| 256 | Stewart Calculo 1 | phybuch | $50,000 | Libros |
| 251 | champiñones Orellana | fungoGenix | $12,000 | Alimentos |
| 258 | NARAYANA | narayana | $20,000 | Casa y Jardín |
| 265 | El Camino de los Reyes | cos-store | $50,000 | Libros |
| 277 | Collar Búho mostacilla | sol-y-luna | $130,000 | Moda, Acc. personales |
| 275 | Tope de puerta amigurumi | sol-y-luna | ~$90,000 | Hogar |
| 262 | Amigurumi | sol-y-luna | $10,000 / $20,000 | Juguetes |
| 263 | Mandalas | sol-y-luna | N/A | Acc. personales |
| 270 | Café orgánico marca Alem | sol-y-luna | ~$40,000 | Alimentos, Bebidas |
| 273 | Panela orgánica | sol-y-luna | ~$25,200 | Alimentos |
| 271 | Árbol de la vida | sol-y-luna | ~$90,000 | Hogar |
| 276 | Separador de libros | sol-y-luna | ~$15,000 | Acc. personales |
| 283 | KZ CASTOR PRO | ziru-acoustics | ~$90,000 | Electrónica, Audio |
| 284 | Doce cuentos peregrinos | legaltech | ~$25,200 | Libros |
| 241 | Producto | N/A | N/A | Sin categoría |
| 249 | Producto 249 | N/A | N/A | Sin categoría |

### Categorías

**Sistema de colecciones (Collections):**

La plataforma usa el modelo de colecciones de Vendure, organizadas jerárquicamente.

**Jerarquía de colecciones** (verificado vía API `collections`):

```
__root_collection__
├── Electrónica
│   ├── Audio
│   ├── Tv y video
│   ├── Celulares y tablets
│   ├── Computadores
│   └── Cámara y fotos
├── Casa y Jardín
│   ├── Muebles
│   └── Plantas
├── Deportes
│   ├── Equipamiento
│   └── Calzado
├── Libros
├── Moda
├── Belleza y cuidado personal
├── Mascotas
├── Juguetes
├── Automotriz
├── Accesorios personales
└── Alimentos
    └── Bebidas
```

**Facetas (atributos de producto)** — verificadas vía API `facets`:

| Faceta | Code | Cantidad valores | Valores |
|---|---|---|---|
| **Categoria** | `category` | 25 | Electrónica, Computadores, Libros, Alimentos, Bebidas, Fotos, Juegos, Deportes al aire libre, Equipamiento, Calzado, Casa y Jardín, Plantas, Muebles, Celulares y tablets, Mascotas, Belleza y cuidado personal, Automotriz, Tv y video, Juguetes, Audio, Moda, Accesorios personales, Hogar, Orgánico, Ropa |
| **Marcas** | `marcas` | 22 | Apple, Logitech, Samsung, Corsair, ADMI, Seagate, Polaroid, Nikkon, Agfa, Manfrotto, Kodak, Sony, nvidia, Rolleiflex, Pinarello, Everlast, Nike, Wilson, Adidas, Converse, Alem |
| **Color** | `color` | 24 | Azul, Rosado, Negro, Blanco, Gris, Marrón, Madera, Amarrillo, Verde, Rojo, Naranja, Morado, Celeste, Turquesa, Violeta, Lila, Fucsia, Verde esmeralda, Verde limón, Azul cielo, Azul marino, Dorado, Plateado |
| **Tipos de plantas** | `tipos-de-plantas` | 2 | Indoor, Outdoor |
| **Género** | `genero` | 2 | Hombre, Mujer |
| **Alimentos** | `alimentos` | 3 | Licores, Endulzante, Orgánico |

**Estructura en API:**

```
Collection
├── CollectionTranslation (nombre, slug, descripción)
├── parent (colección padre, para jerarquías)
├── children (subcolecciones)
├── CollectionBreadcrumb (ruta de navegación)
└── Assets
```

### Colecciones

Las colecciones son las categorías y subcategorías del catálogo. El vendedor asigna sus productos a las colecciones existentes del marketplace (ej: "Electrónica > Audio", "Alimentos > Bebidas"). La plataforma ya tiene definidas las colecciones principales; el vendedor selecciona de la lista existente al crear su producto.

### Inventario

El inventario se maneja a nivel de **ProductVariant** (variante). El vendedor define el stock inicial al crear el producto y puede ajustarlo después. El sistema descuenta automáticamente el stock cuando se confirma un pedido.

### Imágenes

- Las imágenes de productos se almacenan en **AWS S3**: bucket `ecommer-assets.s3.us-east-2.amazonaws.com`.
- El bucket `ecommer-stg-product-images.s3.us-east-2.amazonaws.com` contiene documentos legales (Términos y Condiciones en PDF).
- Cada producto puede tener múltiples imágenes.
- Las imágenes tienen versiones `_preview` (thumbnail) generadas automáticamente.
- El tipo `Asset` en la API maneja metadatos (CoordinateInput para coordenadas, traducciones, tipo MIME).

### Variantes

**Modelo observado:**

```
Product
└── ProductOptionGroup[] (ej: "Cable", "Talla", "Presentación")
    └── ProductOption[] (ej: "3.5mm con Mic", "3.5mm sin Mic")
        └── ProductVariant (combinación específica)
            ├── SKU
            ├── price
            ├── stockLevel
            └── facetValues
```

Cada variante es una combinación única de opciones con su propio precio, SKU y nivel de stock. Ejemplo real observado: el producto "KZ CASTOR PRO BASS EDITION" tiene variante de "Cable" con opciones "3.5mm con Mic" y "3.5mm sin Mic".

---

## 6. Gestión de clientes

**Entidades observadas:**

```
Customer
├── firstName, lastName, emailAddress
├── CustomerCustomFields
├── Address[] (múltiples direcciones)
├── CustomerGroup[] (grupos de clientes)
├── Orders[] (historial de pedidos)
└── CustomerSubscription[] (plan contratado, si es vendedor)
```

**Funcionalidades observadas para el comprador:**

- Registro y perfil de usuario.
- Historial de pedidos con tracking de estados.
- Múltiples direcciones de envío.
- Carrito de compras.
- Checkout con selección de método de pago y dirección.
- Reviews de productos (calificación y comentario).
- Notificaciones de estado de pedido.
- Seguimiento de envío con número de guía (envíos nacionales).

**Estados de pedido visibles para el comprador:**

1. Order received (Recibido)
2. Payment confirmed (Pago confirmado)
3. Order in preparation (En preparación)
4. Order dispatched (Despachado)
5. In transit (En tránsito)
6. Delivered (Entregado)

**No observado:**
- Proceso detallado de registro de comprador (aunque se menciona que es gratuito).
- Si los compradores pueden registrarse con Google además de email.
- Mecanismo de recuperación de contraseña.
- Si los compradores tienen roles o niveles.

---

## 7. Gestión de pedidos

Cuando un cliente compra en su tienda, el pedido aparece en la sección de pedidos del vendedor. El vendedor ve:

- Número de pedido
- Productos comprados (cantidad, variante, precio)
- Datos del comprador y dirección de envío
- Estado del pedido
- Estado del pago
- Costo de envío

**Estados del pedido:**

1. Recibido → 2. Pago confirmado → 3. En preparación → 4. Despachado → 5. En tránsito → 6. Entregado

El vendedor marca el pedido como "En preparación" y luego como "Despachado" cuando entrega el paquete al mensajero. El sistema notifica automáticamente a MESSENGER para la recolección. El pago se libera al vendedor cada 15 días a través de Wompi.

---

## 8. Promociones

Las promociones y descuentos existen en la plataforma (el schema incluye `Promotion`, `CouponCode`), pero **no están disponibles para el vendedor** desde su panel de tienda. Son gestionadas a nivel de plataforma.

Los cupones aplican en el checkout del comprador (errores `CouponCodeInvalidError`, `CouponCodeExpiredError`, `CouponCodeLimitError` confirman que el motor de cupones funciona).

---

## 9. Usuarios

**Tipos de usuario y autenticación:**

| Tipo | Método de registro | Panel |
|---|---|---|
| **Buyer (Customer)** | Email | `ecommer.shop` |
| **Seller** | Google OAuth o Email | `admin.ecommer.shop/dashboard/login` |

**Datos del vendedor:**

El vendedor puede consultar y actualizar su perfil, ver su plan activo, consultar sus facturas y reportes de ventas.

**Funcionalidades del vendedor:**

| Funcionalidad | Descripción |
|---|---|
| `mySubscription` | Ver plan y suscripción activa |
| `myInvoices` | Consultar facturas electrónicas emitidas (DIAN) |
| `getSalesReports` | Ver reportes de ventas |
| `checkProductLimit` | Verificar si alcanzó el límite de productos de su plan |
| `checkVariationLimit` | Verificar si alcanzó el límite de variantes de su plan |
| `storePageProfile` | Administrar perfil público de la tienda |
| `storeFeaturedProductIds` | Elegir productos destacados de la tienda |
| `getWompiTransactionStatus` | Consultar estado de un pago |

---

## 10. Configuración

Lo que el **vendedor** puede configurar de su tienda:

### Perfil de la tienda

- Nombre del negocio
- Slug de la URL (`ecommer.shop/store/{slug}`)
- Logo e imágenes
- Descripción de la tienda
- Productos destacados (`storeFeaturedProductIds`)

### Configuración por tienda (SettingsStore)

```
SettingsStoreScopeType
SettingsStoreFieldDefinition
SettingsStoreInput
SetSettingsStoreValueResult
```

Permite definir campos de configuración personalizados a nivel de tienda.

### Plan y suscripción

Consultable vía `mySubscription`. Define límites de productos, variantes, acceso a IA y facturación electrónica.

### Impuestos

Al crear un producto, el vendedor selecciona la categoría de impuesto:
- Standard Tax (ID: 1) — productos gravados con tarifa plena
- Reduced Tax (ID: 2) — productos con tarifa reducida
- Zero Tax (ID: 3) — productos exentos

El vendedor **no** configura las tasas ni zonas fiscales. Eso es manejado por la plataforma.

### Envíos

El vendedor **no** configura manualmente los métodos de envío. Al crear la tienda, el sistema genera automáticamente un ShippingMethod con código `{store-slug}-shipping` usando el proveedor "Domicilio Messenger Domis". El costo lo calcula el sistema automáticamente.

### Facturación electrónica

Disponible en planes Tienda y Omnichannel. El vendedor puede consultar sus facturas emitidas vía `myInvoices`.

---

## 11. Flujo completo del negocio

```
1. VENDEDOR SE REGISTRA
   ├── Ingresa a admin.ecommer.shop/dashboard/login
   ├── Inicia sesión con Google OAuth o crea cuenta con email
   └── Selecciona plan (Free / Store / Omnichannel)

2. CREA TIENDA
   ├── Define nombre del negocio
   ├── Selecciona categoría
   ├── Define ciudad
   └── La tienda recibe un slug único (ecommer.shop/store/{slug})

3. CONFIGURA TIENDA
   ├── Configuración general (SettingsStore)
   ├── Métodos de pago (Wompi — integrado por defecto)
   ├── Métodos de envío (MESSENGER local, Envia.com nacional)
   ├── Impuestos (configuración de TaxRate por zona)
   └── Facturación electrónica DIAN (Certificado Digital desde $199,900/año)

4. CREA CATEGORÍAS (COLLECTIONS)
   ├── Usa las categorías existentes del marketplace o
   ├── Crea subcolecciones dentro de su tienda
   └── Organiza jerarquía de productos

5. CREA PRODUCTOS
   ├── Nombre, descripción, imágenes (S3)
   ├── Define OptionGroups y Options (variantes)
   ├── Crea ProductVariants con SKU, precio y stock
   ├── Asigna a colecciones
   ├── Asigna facetas (atributos de filtro)
   └── Define stock locations

6. PUBLICA CATÁLOGO
   ├── Productos aparecen en ecommer.shop/search
   ├── Indexados en colecciones del marketplace
   ├── Visibles en la página de tienda (ecommer.shop/store/{slug})
   └── Incluidos en sitemap para SEO

7. CLIENTE COMPRA
   ├── Navega/busca productos en ecommer.shop
   ├── Filtra por categoría, color, tipo de alimento, etc.
   ├── Ve detalle de producto, imágenes, variantes, stock
   ├── Selecciona variante (ej: talla, color) y cantidad
   └── Agrega al carrito

8. PEDIDO (ORDER)
   ├── Cliente procede al checkout
   ├── Ingresa/confirma dirección de envío
   ├── Selecciona método de pago
   ├── Sistema calcula costo de envío automáticamente
   ├── Confirma pedido
   └── Estado inicial: "Order received"

9. PAGO (PAYMENT)
   ├── Procesado por Wompi (PCI-DSS)
   ├── Métodos: TC, PSE, Nequi, Daviplata, corresponsales
   ├── Comisión: 7.9% por transacción
   ├── Estado: "Payment confirmed"
   └── Vendedor notificado del nuevo pedido

10. ENVÍO (FULFILLMENT)
    ├── Vendedor prepara el pedido
    ├── Sistema notifica a MESSENGER (local) o genera guía Envia.com (nacional)
    ├── Operador recoge el paquete
    ├── Estados: "Order in preparation" → "Order dispatched" → "In transit"
    └── Comprador recibe número de guía para rastreo

11. ENTREGA (DELIVERY)
    ├── Paquete llega al comprador
    ├── Estado final: "Delivered"
    ├── Comprador puede dejar review del producto
    ├── Vendedor recibe pago cada 15 días vía Wompi
    └── Factura electrónica DIAN emitida (si el vendedor tiene certificado)

12. POST-VENTA
    ├── Devoluciones: comprador envía solicitud a info@ecommer.shop
    ├── Reembolsos vía Wompi (Refund)
    ├── Soporte 24/7 vía SimetrIA (chat AI)
    ├── Soporte humano: 314 851 8961
    └── Reportes de ventas para contabilidad
```

---

## 12. Reglas de negocio

### Pagos y comisiones

1. **Comisión Wompi:** 7.9% por cada transacción (cubre tarjetas, PSE, corresponsales).
2. **Liquidación:** El vendedor recibe su dinero cada 15 días.
3. **Transferencia gratuita:** Si usa Nequi, Bancolombia o banco con BRE-B registrado. Otros bancos: costo asumido por la tienda.
4. **Reclamos/contracargos:** Wompi notifica al vendedor, quien tiene 7 días para demostrar la entrega. Se recomienda guardar documentación de ventas por al menos 1 año.
5. **Seguridad:** Pagos monitoreados 24/7 con segunda clave para retiros.

### Planes y límites

**Verificado vía API `allPlans`:**

| Límite | Free | Tienda | Omnichannel |
|---|---|---|---|
| Productos (max_products) | 15 | 500 | 1,500 |
| Variantes (max_variations) | 250 | 5,000 | 15,000 |
| Acceso IA / SimetrIA (ai_access) | No | Sí | Sí |
| Facturación electrónica DIAN (electronic_billing) | No | Sí | Sí |
| Precio mensual | $0 COP | $29,900 COP | $99,900 COP |
| BillingInterval | monthly | monthly | monthly |

- **Prueba gratuita:** Los primeros 3 meses sin cargo mensual de plataforma (mencionado en landing de sellers; no verificado en API).
- Los límites se consultan en tiempo real con las queries `checkProductLimit` y `checkVariationLimit`.
- La plataforma solo gana cuando el vendedor vende (modelo alineado de incentivos, comisión Wompi 7.9%).

### Envíos

1. **Envíos locales (Popayán):** MESSENGER. Costo asumido por el comprador, calculado por distancia.
2. **Envíos nacionales:** Envia.com. Costo calculado por peso, dimensiones, origen, destino y transportadora.
3. El vendedor no configura manualmente el costo de envío; el sistema lo calcula automáticamente.

### Facturación electrónica

1. **Persona natural en régimen no responsable de IVA:** No está obligada a facturar electrónicamente.
2. **Persona jurídica:** Obligada por ley a emitir factura electrónica.
3. **Certificado Digital DIAN:** Cuesta $199,900 COP/año (o en cuotas mensuales con permanencia).
4. La integración con DIAN es nativa en la plataforma.

### Devoluciones y garantías

1. Las solicitudes de devolución se envían a `info@ecommer.shop`.
2. Ecommer revisa el caso según la normativa aplicable y, si aprueba, lo remite al vendedor.
3. Documentos legales disponibles: Términos y Condiciones, Garantía, Retracto, Reversión del pago.

### Cumplimiento normativo

- **PCI DSS:** Cumplimiento a través de Wompi.
- **DIAN:** Resolución 0227/2025.
- **Ley 1581:** Protección de datos personales.
- **Estatuto del Consumidor:** Ley 1480 de 2011.

---

## 13. Preguntas frecuentes

### ¿Cómo crear una tienda?

Ingresa a `https://admin.ecommer.shop/dashboard/login`, inicia sesión con Google o regístrate con email. Solo necesitas un correo electrónico para comenzar. Selecciona tu plan (Free recomendado para empezar), define el nombre del negocio, categoría y ciudad. La tienda se crea inmediatamente y puedes empezar a listar productos.

### ¿Cómo publicar un producto?

Desde el panel del vendedor (`admin.ecommer.shop`), accede a la sección de catálogo. Define nombre, descripción, precio, imágenes, variantes (si aplican), stock y categoría/colección. El producto aparecerá en el marketplace al publicarse.

### ¿Cómo configurar impuestos?

El vendedor selecciona la categoría de impuesto al crear cada producto (Standard Tax, Reduced Tax o Zero Tax). Las tasas y zonas fiscales las gestiona la plataforma, no el vendedor.

### ¿Es realmente gratis?

Sí. El plan Free es gratuito para siempre. Solo pagas la comisión de Wompi (7.9% por transacción). Los primeros 3 meses no pagas cargo mensual incluso en planes pagos.

### ¿Qué necesito para vender?

Solo un correo electrónico. Si quieres operar como empresa, puedes agregar la información tributaria después.

### ¿Necesito saber programar?

No. "Si sabes usar Facebook o WhatsApp, sabes usar Ecommer. Subir un producto es tan fácil como subir una foto a Instagram."

### ¿Cómo recibo el dinero de mis ventas?

Cada 15 días a través de Wompi. Si usas Nequi, Bancolombia o banco con BRE-B registrado, sin costo adicional.

### ¿Cómo funcionan los envíos en Popayán?

Alianza con MESSENGER. Al recibir un pedido, el sistema notifica automáticamente al mensajero para que recoja el paquete y lo entregue. El costo lo asume el comprador.

### ¿Es obligatoria la facturación electrónica?

No para empezar si eres persona natural en régimen no responsable de IVA. Personas jurídicas están obligadas por ley. La plataforma ofrece el servicio de facturación electrónica con Certificado Digital DIAN desde $199,900/año.

---

## 14. Consideraciones para IA

### Cómo responder preguntas

1. **Basarse en este documento como fuente primaria de verdad funcional.**
2. Siempre distinguir entre lo observado y lo inferido. Si la respuesta no está en este documento, indicar "No tengo suficiente información para responder esto con certeza."
3. Para preguntas sobre la interfaz de usuario, advertir que la información proviene de datos de API, no de la UI renderizada, ya que el panel del vendedor es una SPA no indexable.
4. Recordar que ECOMMER es un producto **colombiano**, enfocado en microempresarios de Popayán y Cauca. El contexto cultural y regulatorio es colombiano.
5. Los precios siempre están en **pesos colombianos (COP)**.
6. La plataforma usa **español** como idioma principal, con **inglés** como segundo idioma.
7. El vendedor solo ve y gestiona **su propia tienda**. No tiene acceso a otras tiendas, configuración global ni administración de la plataforma.

### Qué no asumir

1. **No asumir funcionalidades de otros ecommerce** (Shopify, WooCommerce, MercadoLibre). ECOMMER tiene sus propias reglas.
2. **No asumir dominios personalizados** disponibles para tiendas.
3. **No asumir integraciones de pago adicionales** a Wompi.
4. **No asumir transportadoras específicas** más allá de MESSENGER (local) y Envia.com (nacional).
5. **No asumir secciones de la interfaz** que no hayan sido observadas directamente.
6. **No asumir precios en otras monedas.**
7. **No asumir soporte para ventas internacionales** (aunque la misión lo mencione, la implementación observada es enteramente colombiana).
8. **No inventar pasos de UI** (ej: "haz clic en el botón X del menú Y") sin haberlos observado.

### Qué información siempre validar

1. **Planes y precios:** Pueden cambiar. Los valores observados son de julio 2026.
2. **Comisión Wompi:** 7.9% al momento de esta exploración.
3. **Disponibilidad de categorías:** Las 10 categorías principales están confirmadas. Subcategorías pueden expandirse.
4. **Estados de pedido:** Los 6 estados observados son del frontend de comprador. El backend (Vendure) tiene un sistema de state machine más granular con transiciones configurables.
5. **Certificado Digital DIAN:** $199,900 COP/año al momento de esta exploración.

### Qué módulos dependen de otros

```
Seller ──> Plan (CustomerSubscription)
Store ──> Product ──> ProductVariant ──> StockLevel
Product ──> Collection (categoría)
Product ──> FacetValue (atributos de filtro)
Product ──> ProductOptionGroup ──> ProductOption (variantes)
ProductVariant ──> Asset (imágenes)
Order ──> Customer
Order ──> ProductVariant (vía OrderLine)
Order ──> Payment (Wompi)
Order ──> Fulfillment (envío MESSENGER)
ProductReview ──> Product ──> Customer
Invoice ──> Order ──> Seller
```

---

## Errata / Problemas detectados

Durante la exploración de la API (julio 2026), se detectaron los siguientes comportamientos:

1. **`searchStores` query rota:** Devuelve error `syntax error at or near ":"` — posible bug en el resolver custom que construye SQL a partir del input GraphQL. La búsqueda de tiendas no funciona vía API en este momento.

2. **Endpoints que requieren autenticación:** Las queries de envío/logística (`getCitiesDepartament`, `getCitiesOrigin`, `calculateDeliveryCost`, etc.) y las queries de seller (`mySubscription`, `myInvoices`, `getSalesReports`) requieren sesión autenticada. No se pudieron probar sin credenciales.

3. **Precios API vs Marketplace:** Los precios en la API (`/shop-api`) difieren de los mostrados en el marketplace. Ej: champiñones Orellana: API = $12,000 COP, Marketplace = $14,280 COP. Esto sugiere un markup o recálculo con impuestos en el frontend.

4. **37 métodos de envío duplicados:** Cada tienda recibe su propio ShippingMethod con el mismo nombre "Domicilio Messenger Domis" y descripción idéntica. Posible problema de escalado o diseño intencional para tracking por tienda. Algunos códigos están duplicados (`alem-shipping` aparece 3 veces con IDs 35, 62, 71).

5. **Productos sin variantes:** Los productos con ID 241, 249 y 263 (Mandalas) no tienen variantes (`variants: []`). Esto impediría su compra ya que Vendure requiere variantes para el checkout.

---

## Notas técnicas

### Stack tecnológico observado

| Capa | Tecnología |
|---|---|
| Frontend (Marketplace) | Next.js (React) — `ecommer.shop` |
| Frontend (Vendedor) | Next.js (React) — `admin.ecommer.shop` |
| Backend | Vendure (Node.js/TypeScript headless commerce) |
| API | GraphQL (`/shop-api`) |
| Almacenamiento | AWS S3 (`ecommer-assets`, `ecommer-stg-product-images`) |
| CDN/Proxy | Cloudflare |
| Pagos | Wompi (Bancolombia) |
| Logística local | MESSENGER |
| Logística nacional | Envia.com |
| Facturación | DIAN |
| IA | SimetrIA (custom, integrado vía API `ChatResponse`) |
| i18n | Español (es), Inglés (en) |
| Infraestructura | Azure (mencionado en About Us como proveedor cloud) |

### URLs relevantes

| URL | Propósito |
|---|---|
| `https://admin.ecommer.shop` | Panel del vendedor |
| `https://admin.ecommer.shop/dashboard/login` | Login del vendedor |
| `https://ecommer.shop` | Marketplace público |
| `https://ecommer.shop/es/sellers` | Landing para vendedores |
| `https://ecommer.shop/about-us` | Información corporativa |
| `https://ecommer.shop/users` | Información para compradores |
| `https://ecommer.shop/es/legal/terms` | Términos y condiciones |
| `https://ecommer.shop/es/legal/privacy` | Política de privacidad |

### Contacto

| Canal | Dato |
|---|---|
| Teléfono soporte | 314 851 8961 |
| WhatsApp | 3223647362 |
| Email soporte | info@ecommer.shop |
| Email devoluciones | info@ecommer.shop |
| Dirección | Carrera 2a 3N 23, Antiguo Liceo, Popayán, Cauca, CO |
| Horario | Lunes a Viernes, 8:00-12:00 y 14:00-17:00 |
