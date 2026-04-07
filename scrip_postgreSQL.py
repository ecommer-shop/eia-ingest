import psycopg2
import json
import unicodedata
import re
from config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD, PG_SSL

def generate_product_slug(name: str) -> str:
    """
    Normaliza el nombre del producto para URLs:
    Quita tildes, pasa a minúsculas y reemplaza espacios/símbolos por guiones.
    """
    # 1. Quitar acentos y tildes (Normalización NFKD)
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    # 2. Pasar a minúsculas
    normalized = normalized.lower()
    # 3. Reemplazar cualquier caracter que no sea alfanumérico por un guion '-'
    slug = re.sub(r'[^a-z0-9]+', '-', normalized)
    # 4. Quitar guiones extra al principio o al final
    return slug.strip('-')

def extract_product_catalog():
    print("🔌 Conectando a PostgreSQL para extraer productos en idiomas: 'es' y 'en'...")
    
    # Nota Arquitectónica: Vendure ya guarda un 'slug' nativo en la tabla product_translation.
    # Si en el futuro hay nombres duplicados que rompan la URL, te sugiero añadir 'pt.slug' al SELECT.
    query = """
        SELECT 
            p.id AS product_id,
            pt."languageCode" AS language,
            pt.name AS product_name,
            pt.description AS product_description,
            COALESCE(string_agg(DISTINCT ct.name, ', '), 'Sin categoría') AS categories,
            COALESCE(string_agg(DISTINCT fvt.name, ', '), 'Sin atributos') AS attributes,
            COALESCE(string_agg(DISTINCT pv.sku, ', '), '') AS skus,
            COALESCE(string_agg(DISTINCT pot.name, ', '), '') AS options
            
        FROM product p
        JOIN product_translation pt ON p.id = pt."baseId" AND pt."languageCode" IN ('es', 'en')
        LEFT JOIN product_facet_values_facet_value pfv ON p.id = pfv."productId"
        LEFT JOIN facet_value_translation fvt ON pfv."facetValueId" = fvt."baseId" AND fvt."languageCode" = pt."languageCode"
        LEFT JOIN product_variant pv ON p.id = pv."productId"
        LEFT JOIN collection_product_variants_product_variant cpv ON pv.id = cpv."productVariantId"
        LEFT JOIN collection_translation ct ON cpv."collectionId" = ct."baseId" AND ct."languageCode" = pt."languageCode"
        LEFT JOIN product_variant_options_product_option pv_opt ON pv.id = pv_opt."productVariantId"
        LEFT JOIN product_option_translation pot ON pv_opt."productOptionId" = pot."baseId" AND pot."languageCode" = pt."languageCode"
        
        WHERE p."deletedAt" IS NULL
        
        GROUP BY 
            p.id, pt."languageCode", pt.name, pt.description;
    """
    
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, 
            user=PG_USER, password=PG_PASSWORD, sslmode=PG_SSL
        )
        cur = conn.cursor()
        
        cur.execute(query)
        rows = cur.fetchall()
        
        extracted_data = []
        base_url = "https://stg.ecommer.shop"
        
        for row in rows:
            product_id, language, name, description, categories, attributes, skus, options = row
            
            # --- NUEVA LÓGICA DE URL ---
            slug = generate_product_slug(name)
            product_url = f"{base_url}/{language}/product/{slug}"
            
            # 1. EL TEXTO PARA LA IA (Contexto enriquecido con la URL para el LLM)
            text_to_embed = f"[{language.upper()}] Producto: {name}. "
            text_to_embed += f"URL de compra: {product_url}. "
            
            if categories != 'Sin categoría':
                text_to_embed += f"Categorías: {categories}. "
            if attributes != 'Sin atributos':
                text_to_embed += f"Atributos generales: {attributes}. "
            if options:
                text_to_embed += f"Opciones disponibles (Tallas/Tipos): {options}. "
            
            text_to_embed += f"Descripción: {description}"
            
            # 2. EL PAYLOAD (Metadatos duros para Qdrant)
            payload = {
                "product_id": product_id,
                "language": language,
                "document_type": "product_base",
                "name": name,          # Nombre exacto preservado
                "url": product_url,    
                "categories": categories.split(", ") if categories != 'Sin categoría' else [],
                "attributes": attributes.split(", ") if attributes != 'Sin atributos' else [],
                "skus": skus.split(", ") if skus else [],
                "options": options.split(", ") if options else []
            }
            
            extracted_data.append({
                "text": text_to_embed,
                "payload": payload
            })
            
        cur.close()
        conn.close()
        
        print(f"✅ Se extrajeron y formatearon {len(extracted_data)} productos/idiomas exitosamente.")
        
        # Validación visual rápida del primer elemento
        if extracted_data:
            print("\n👀 --- MUESTRA DEL PRIMER PRODUCTO ---")
            print("📝 TEXTO VECTORIZABLE:")
            print(f"   {extracted_data[0]['text']}")
            print("\n🏷️  PAYLOAD:")
            print(f"   {json.dumps(extracted_data[0]['payload'], indent=2, ensure_ascii=False)}")
            print("--------------------------------------\n")
            
        return extracted_data

    except Exception as e:
        print(f"❌ Error crítico en la extracción: {e}")
        return []

if __name__ == "__main__":
    extract_product_catalog()