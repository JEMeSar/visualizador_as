import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np

# Configuración de la página
st.set_page_config(
    page_title="Línea Temporal de Contratos",
    page_icon="",
    layout="wide"
)

def load_data(file_path):
    """Cargar y procesar datos del Excel"""
    try:
        # Leer el archivo Excel
        df = pd.read_excel(file_path)
        
        # Mostrar columnas disponibles para debug
        st.sidebar.write("Columnas encontradas:", list(df.columns))
        
        # Procesar las fechas de manera más robusta
        df['Falta'] = pd.to_datetime(df['Falta'], errors='coerce')
        df['Fbaja'] = pd.to_datetime(df['Fbaja'], errors='coerce')
        
        # Limpiar datos
        df = df.dropna(subset=['DNI', 'CATEGORIA', 'Falta', 'Fbaja'])
        
        # Asegurar que DNI sea string
        df['DNI'] = df['DNI'].astype(str).str.zfill(9)
        df['CATEGORIA'] = df['CATEGORIA'].astype(str).str.strip()
        
        # Calcular duración
        df['Duracion'] = (df['Fbaja'] - df['Falta']).dt.days
        
        # Filtrar registros con duración negativa o muy larga (posibles errores)
        df = df[(df['Duracion'] >= 0) & (df['Duracion'] <= 10000)]
        
        return df
    except Exception as e:
        st.error(f"Error al cargar el archivo: {e}")
        st.error("Verifica que el archivo tenga las columnas: DNI, CATEGORIA, Falta, Fbaja")
        return None

def calculate_active_contracts_by_month(df, categorias_seleccionadas):
    """Calcular contratos activos por mes y categoría"""
    if df is None or df.empty:
        return {}
    
    # Filtrar por categorías seleccionadas
    df_filtrado = df[df['CATEGORIA'].isin(categorias_seleccionadas)]
    
    # Obtener rango de fechas
    fecha_min = df_filtrado['Falta'].min()
    fecha_max = df_filtrado['Fbaja'].max()
    
    # Generar meses
    meses = pd.date_range(start=fecha_min.replace(day=1), 
                         end=fecha_max.replace(day=1), 
                         freq='MS')
    
    resultados = {}
    
    for categoria in categorias_seleccionadas:
        df_cat = df_filtrado[df_filtrado['CATEGORIA'] == categoria]
        contratos_por_mes = []
        
        for mes in meses:
            # Contar contratos activos en ese mes
            activos = df_cat[
                (df_cat['Falta'] <= mes) & 
                (df_cat['Fbaja'] >= mes)
            ].shape[0]
            contratos_por_mes.append(activos)
        
        resultados[categoria] = {
            'meses': meses,
            'contratos': contratos_por_mes
        }
    
    return resultados

def create_timeline_chart(df, categorias_seleccionadas):
    """Crear el gráfico de línea temporal"""
    if df is None or df.empty or not categorias_seleccionadas:
        return None
    
    # Filtrar datos
    df_filtrado = df[df['CATEGORIA'].isin(categorias_seleccionadas)].copy()
    
    if df_filtrado.empty:
        st.warning("No hay datos para las categorías seleccionadas")
        return None
    
    # Crear figura
    fig = go.Figure()
    
    # Obtener rango de fechas
    fecha_min = df_filtrado['Falta'].min()
    fecha_max = df_filtrado['Fbaja'].max()
    
    y_position = 0
    categoria_positions = {}
    
    # Colores para categorías
    colors = px.colors.qualitative.Set3
    
    for i, categoria in enumerate(categorias_seleccionadas):
        df_cat = df_filtrado[df_filtrado['CATEGORIA'] == categoria]
        
        if df_cat.empty:
            continue
            
        categoria_positions[categoria] = y_position
        
        # Agrupar por DNI
        for dni in df_cat['DNI'].unique():
            df_dni = df_cat[df_cat['DNI'] == dni]
            
            for _, contrato in df_dni.iterrows():
                # Verificar que las fechas sean válidas
                if pd.isna(contrato['Falta']) or pd.isna(contrato['Fbaja']):
                    continue
                    
                # Agregar barra para cada contrato
                fig.add_trace(go.Scatter(
                    x=[contrato['Falta'], contrato['Fbaja']],
                    y=[y_position, y_position],
                    mode='lines',
                    line=dict(width=10, color=colors[i % len(colors)]),
                    hovertemplate=(
                        f"<b>{categoria}</b><br>"
                        f"DNI: {dni}<br>"
                        f"Inicio: {contrato['Falta'].strftime('%d/%m/%Y')}<br>"
                        f"Fin: {contrato['Fbaja'].strftime('%d/%m/%Y')}<br>"
                        f"Duración: {contrato['Duracion']} días"
                        "<extra></extra>"
                    ),
                    showlegend=False
                ))
            
            y_position += 1
        
        # Añadir separación entre categorías
        y_position += 2
    
    # Añadir líneas verticales para cambios de año
    if not pd.isna(fecha_min) and not pd.isna(fecha_max):
        años = range(fecha_min.year + 1, fecha_max.year + 1)
        for año in años:
            fecha_año = pd.Timestamp(año, 1, 1)
            fig.add_shape(
                type="line",
                x0=fecha_año,
                x1=fecha_año,
                y0=0,
                y1=y_position,
                line=dict(color="red", width=3),
            )
            # Añadir anotación del año
            fig.add_annotation(
                x=fecha_año,
                y=y_position,
                text=str(año),
                showarrow=False,
                yshift=10,
                font=dict(color="red", size=12, family="Arial Black")
            )
    
    # Configurar layout
    fig.update_layout(
        title="Línea Temporal de Contratos por Categoría y Persona",
        xaxis_title="Fecha",
        yaxis_title="Contratos",
        height=max(600, y_position * 15),
        showlegend=False,
        xaxis=dict(
            tickformat='%m/%y',
            dtick='M1'
        ),
        yaxis=dict(
            tickmode='array',
            tickvals=[categoria_positions.get(cat, 0) + 
                     df_filtrado[df_filtrado['CATEGORIA'] == cat]['DNI'].nunique()/2 
                     for cat in categorias_seleccionadas if cat in categoria_positions],
            ticktext=[cat for cat in categorias_seleccionadas if cat in categoria_positions]
        )
    )
    
    return fig

def create_active_contracts_chart(datos_activos):
    """Crear gráfico de contratos activos por mes"""
    if not datos_activos:
        return None
    
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set3
    
    for i, (categoria, data) in enumerate(datos_activos.items()):
        fig.add_trace(go.Scatter(
            x=data['meses'],
            y=data['contratos'],
            mode='lines+markers+text',
            name=categoria,
            line=dict(color=colors[i % len(colors)], width=3),
            text=data['contratos'],
            textposition='top center',
            textfont=dict(size=10, color='green'),
            hovertemplate=(
                f"<b>{categoria}</b><br>"
                "Fecha: %{x|%m/%Y}<br>"
                "Contratos activos: %{y}"
                "<extra></extra>"
            )
        ))
    
    # Añadir líneas verticales para cambios de año
    if datos_activos:
        primer_categoria = list(datos_activos.keys())[0]
        meses = datos_activos[primer_categoria]['meses']
        
        años_únicos = sorted(set(mes.year for mes in meses))
        for año in años_únicos[1:]:  # Empezar desde el segundo año
            fecha_año = pd.Timestamp(año, 1, 1)
            fig.add_shape(
                type="line",
                x0=fecha_año,
                x1=fecha_año,
                y0=0,
                y1=1,
                yref="paper",
                line=dict(color="red", width=2, dash="dash"),
            )
    
    fig.update_layout(
        title="Contratos Activos",
        xaxis_title="Fecha",
        yaxis_title="Número de Contratos Activos",
        height=400,
        xaxis=dict(
            tickformat='%m/%y',
            dtick='M3'  # Cada 3 meses
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig

def main():
    st.title("Línea Temporal de Contratos por Categoría y Persona")
    
    # Sidebar para cargar archivo
    st.sidebar.header("Configuración")
    
    uploaded_file = st.sidebar.file_uploader(
        "Cargar archivo Excel",
        type=['xlsx', 'xls'],
        help="Selecciona el archivo accion_social.xlsx"
    )
    
    if uploaded_file is not None:
        # Cargar datos
        with st.spinner("Cargando datos..."):
            df = load_data(uploaded_file)
        
        if df is not None:
            # Mostrar información básica
            st.sidebar.success(f"✅ Datos cargados: {len(df)} contratos")
            st.sidebar.write(f"📅 Período: {df['Falta'].min().strftime('%d/%m/%Y')} - {df['Fbaja'].max().strftime('%d/%m/%Y')}")
            
            # Filtros
            st.sidebar.header("Filtros")
            categorias_disponibles = sorted(df['CATEGORIA'].unique())
            categorias_seleccionadas = st.sidebar.multiselect(
                "Seleccionar categorías:",
                categorias_disponibles,
                default=categorias_disponibles,
                help="Selecciona las categorías que quieres visualizar"
            )
            
            if categorias_seleccionadas:
                # Calcular datos
                datos_activos = calculate_active_contracts_by_month(df, categorias_seleccionadas)
                
                # Mostrar estadísticas
                col1, col2, col3 = st.columns(3)
                
                df_filtrado = df[df['CATEGORIA'].isin(categorias_seleccionadas)]
                
                with col1:
                    st.metric("Total Contratos", len(df_filtrado))
                
                with col2:
                    st.metric("Total Personas", df_filtrado['DNI'].nunique())
                
                with col3:
                    st.metric("Categorías Seleccionadas", len(categorias_seleccionadas))
                
                # Gráfico de contratos activos
                st.header("Contratos Activos por Mes")
                fig_activos = create_active_contracts_chart(datos_activos)
                if fig_activos:
                    st.plotly_chart(fig_activos, use_container_width=True)
                
                # Gráfico de línea temporal
                st.header("Línea Temporal Detallada")
                fig_timeline = create_timeline_chart(df, categorias_seleccionadas)
                if fig_timeline:
                    st.plotly_chart(fig_timeline, use_container_width=True)
                
                # Tabla de resumen por categoría
                st.header("Resumen por Categoría")
                resumen_categorias = []
                for categoria in categorias_seleccionadas:
                    df_cat = df_filtrado[df_filtrado['CATEGORIA'] == categoria]
                    resumen_categorias.append({
                        'Categoría': categoria,
                        'Contratos': len(df_cat),
                        'Personas': df_cat['DNI'].nunique(),
                        'Duración Promedio (días)': round(df_cat['Duracion'].mean(), 1)
                    })
                
                df_resumen = pd.DataFrame(resumen_categorias)
                st.dataframe(df_resumen, use_container_width=True)
                
                # Opción para descargar datos filtrados
                st.header("💾 Descargar Datos")
                csv = df_filtrado.to_csv(index=False)
                st.download_button(
                    label="Descargar datos filtrados como CSV",
                    data=csv,
                    file_name=f"contratos_filtrados_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime='text/csv'
                )
            
            else:
                st.warning("⚠️ Selecciona al menos una categoría para visualizar los datos.")
    
    else:
        st.info("Carga el archivo Excel usando el panel lateral.")
        
        # Mostrar instrucciones
        st.markdown("""
        ### Instrucciones:
        
        1. **Carga el archivo Excel** usando el botón en el panel lateral
        2. **Selecciona las categorías** que quieres visualizar
        3. **Gráficos** interactivos:
           - **Gráfico de contratos activos**: Muestra el número de contratos activos por mes
           - **Línea temporal**: Muestra cada contrato individual por persona
        4. **Descarga de datos** filtrados
        
        ### Características:
        - **Líneas rojas verticales** marcan el cambio de año
        - **Números verdes** muestran contratos activos por mes
        - **Filtros interactivos** por categoría
        - **Tooltips informativos** al pasar el ratón
        - **Descarga de datos** en formato CSV
        """)

if __name__ == "__main__":
    main()