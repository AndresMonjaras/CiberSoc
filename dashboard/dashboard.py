import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, dash_table
from dash.dependencies import Input, Output
from datetime import datetime
import boto3
import io
import base64

app = Dash(__name__)
app.title = "Dashboard"

# CONFIG AWS
bucket = "bucket-proyecto-big-data"
s3 = boto3.client("s3")

# PALETA DE COLORES
C_BG = "#050505"
C_PAPER = "#121212"
C_TEXT = "#E0E0E0"
C_TEXT_MUTED = "#888888"
C_PRIMARY = "#00D2FF"
C_DANGER = "#FF003C"
C_BORDER = "#2A2A2A"

NEON_PALETTE = ["#00D2FF", "#FF003C", "#B200FF", "#00FF66", "#FFD700", "#FF7300", "#FF00FF", "#00FFFF"]

# RUTAS DE ÍCONOS VECTORIALES
PATH_SHIELD = "M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"
PATH_WARNING = "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"
PATH_DB = "M12 3c-4.97 0-9 1.79-9 4s4.03 4 9 4 9-1.79 9-4-4.03-4-9-4zm0 14c-4.97 0-9-1.79-9-4v2c0 2.21 4.03 4 9 4s9-1.79 9-4v-2c0 2.21-4.03 4-9 4zm0-5c-4.97 0-9-1.79-9-4v2c0 2.21 4.03 4 9 4s9-1.79 9-4v-2c0 2.21-4.03 4-9 4z"
PATH_GLOBE = "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"
PATH_BUG = "M20 8h-2.81c-.45-.78-1.07-1.45-1.82-1.96L17 4.41 15.59 3l-2.17 2.17C12.96 5.06 12.49 5 12 5c-.49 0-.96.06-1.41.17L8.41 3 7 4.41l1.62 1.63C7.88 6.55 7.26 7.22 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1c0 .34.04.67.09 1H4v2h2.81c1.04 1.79 2.97 3 5.19 3s4.15-1.21 5.19-3H20v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8zm-6 8h-4v-2h4v2zm0-4h-4v-2h4v2z"
PATH_BUILDING = "M12 7V3H2v18h20V7H12zM6 19H4v-2h2v2zm0-4H4v-2h2v2zm0-4H4V9h2v2zm0-4H4V5h2v2zm4 12H8v-2h2v2zm0-4H8v-2h2v2zm0-4H8V9h2v2zm0-4H8V5h2v2zm10 12h-8v-2h2v-2h-2v-2h2v-2h-2V9h8v10zm-2-8h-2v2h2v-2zm0 4h-2v2h2v-2z"
PATH_NETWORK = "M20.57 14.86L22 13.43 20.57 12 17 15.57 8.43 7 12 3.43 10.57 2 9.14 3.43 7.71 2 5.57 4.14 4.14 2.71 2.71 4.14l1.43 1.43L2 7.71l1.43 1.43L2 10.57 3.43 12 7 8.43 15.57 17 12 20.57 13.43 22l1.43-1.43 1.43 1.43L18.43 20l2.14-2.14 1.43 1.43 1.43-1.43-1.43-1.43 1.43-1.43z"
PATH_LAYER = "M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63-1.27-7.38 5.74zM12 16l7.36-5.73L21 9l-9-7-9 7 1.63 1.27L12 16z"
PATH_STOPWATCH = "M15 1H9v2h6V1zm-4 13h2V8h-2v6zm8.03-6.61l1.42-1.42c-.43-.51-.9-.99-1.41-1.41l-1.42 1.42C16.07 4.74 14.12 4 12 4c-4.97 0-9 4.03-9 9s4.02 9 9 9 9-4.03 9-9c0-2.12-.74-4.07-1.97-5.61zM12 20c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z"
PATH_CLOCK = "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"

# Dibujar íconos SVG codificados en Base64
def svg_icon(path, color="#FFFFFF", size=22, margin_right="10px"):
    svg_raw = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}"><path d="{path}" fill="{color}"/></svg>'
    
    # Codificación a Base64
    encoded_svg = base64.b64encode(svg_raw.encode('utf-8')).decode('utf-8')
    
    return html.Img(
        src=f"data:image/svg+xml;base64,{encoded_svg}",
        style={
            "width": f"{size}px", 
            "height": f"{size}px", 
            "marginRight": margin_right, 
            "verticalAlign": "middle"
        }
    )

# ESTILOS
ROW_STYLE = {
    "display": "flex",
    "flexDirection": "row",
    "gap": "20px", 
    "marginBottom": "20px"
}

CARD_STYLE = {
    "backgroundColor": C_PAPER,
    "padding": "25px 20px", 
    "borderRadius": "12px",
    "flex": "1", 
    "border": f"1px solid {C_BORDER}",
    "boxShadow": f"0px 4px 15px rgba(0, 210, 255, 0.05)",
    "textAlign": "center"
}

GRAPH_CONTAINER_STYLE = {
    "backgroundColor": C_PAPER,
    "padding": "20px",
    "borderRadius": "12px",
    "flex": "1",
    "border": f"1px solid {C_BORDER}",
    "boxShadow": f"0px 4px 15px rgba(0, 0, 0, 0.5)"
}

WARNING_STYLE_VISIBLE = {
    "backgroundColor": "#2A0000",
    "border": f"1px solid {C_DANGER}",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "20px",
    "color": "#FF6666",
    "display": "block",
    "boxShadow": f"0px 0px 20px rgba(255, 0, 60, 0.4)"
}

WARNING_STYLE_HIDDEN = {"display": "none"}

def font_style(size, weight, color):
    return {"fontSize": size, "fontWeight": weight, "color": color, "margin": "0", "fontFamily": "Segoe UI, Arial, sans-serif"}

# LAYOUT
app.layout = html.Div(
    style={"backgroundColor": C_BG, "padding": "30px", "fontFamily": "Segoe UI, Arial, sans-serif", "color": C_TEXT, "minHeight": "100vh"},
    children=[
        # ENCABEZADO
        html.Div([
            html.H1("SOC Dashboard - Monitoreo de Red", style=font_style("2.2rem", "700", C_TEXT)),
            html.P("Monitoreo de red en tiempo real con análisis dimensional.", style={**font_style("1.1rem", "400", C_TEXT_MUTED), "marginTop": "10px"}),
            html.Div(id="hora_actualizacion", style={**font_style("0.9rem", "600", C_PRIMARY), "marginTop": "5px"})
        ], style={"marginBottom": "30px", "borderBottom": f"1px solid {C_BORDER}", "paddingBottom": "15px", "textAlign": "center"}),

        dcc.Interval(id="interval", interval=5000, n_intervals=0),
        dcc.Interval(id="interval_warning", interval=1000, n_intervals=0),
        dcc.Store(id="store_ataque_ts", data=None),

        # BANNER DE ADVERTENCIA
        html.Div(
            id="warning_banner",
            style=WARNING_STYLE_HIDDEN,
            children=[
                html.Div([
                    html.Span([
                        svg_icon(PATH_WARNING, color=C_DANGER, size=28, margin_right="10px"),
                        html.Span("ATAQUE DETECTADO Y BLOQUEADO", style={"verticalAlign": "middle"})
                    ], style=font_style("1.5rem", "bold", C_DANGER)),
                    html.Span(id="warning_countdown", style={"float": "right", "fontSize": "14px", "color": C_DANGER, "marginTop": "5px"})
                ], style={"marginBottom": "15px"}),
                html.Div(id="warning_contenido")
            ]
        ),

        # KPIs (4 tarjetas)
        html.Div(style=ROW_STYLE, children=[
            html.Div([
                html.Div([
                    svg_icon(PATH_DB, color="#FFFFFF", size=18, margin_right="8px"),
                    html.Span("TOTAL REGISTROS", style={"verticalAlign": "middle"})
                ], style=font_style("0.85rem", "600", C_TEXT_MUTED)),
                html.H2(id="kpi_total", style={**font_style("2.5rem", "700", C_PRIMARY), "marginTop": "10px"})
            ], style=CARD_STYLE),
            
            html.Div([
                html.Div([
                    svg_icon(PATH_GLOBE, color="#FFFFFF", size=18, margin_right="8px"),
                    html.Span("IPS ÚNICAS", style={"verticalAlign": "middle"})
                ], style=font_style("0.85rem", "600", C_TEXT_MUTED)),
                html.H2(id="kpi_ips", style={**font_style("2.5rem", "700", C_PRIMARY), "marginTop": "10px"})
            ], style=CARD_STYLE),
            
            html.Div([
                html.Div([
                    svg_icon(PATH_BUG, color="#FFFFFF", size=18, margin_right="8px"),
                    html.Span("ATAQUES DETECTADOS", style={"verticalAlign": "middle"})
                ], style=font_style("0.85rem", "600", C_TEXT_MUTED)),
                html.H2(id="kpi_ataques", style={**font_style("2.5rem", "700", C_DANGER), "marginTop": "10px"})
            ], style=CARD_STYLE),
            
            html.Div([
                html.Div([
                    svg_icon(PATH_BUILDING, color="#FFFFFF", size=18, margin_right="8px"),
                    html.Span("DEPARTAMENTOS", style={"verticalAlign": "middle"})
                ], style=font_style("0.85rem", "600", C_TEXT_MUTED)),
                html.H2(id="kpi_departamentos", style={**font_style("2.5rem", "700", C_PRIMARY), "marginTop": "10px"})
            ], style=CARD_STYLE),
        ]),

        # FILA 1: Predicciones y Departamentos
        html.Div(style=ROW_STYLE, children=[
            html.Div([
                html.H3("Clasificación IA (Tráfico)", style=font_style("1.2rem", "600", C_TEXT)),
                dcc.Graph(id="grafica_predicciones", config={"displayModeBar": False})
            ], style=GRAPH_CONTAINER_STYLE),

            html.Div([
                html.H3("Tráfico por Departamento", style=font_style("1.2rem", "600", C_TEXT)),
                dcc.Graph(id="grafica_departamentos", config={"displayModeBar": False})
            ], style=GRAPH_CONTAINER_STYLE),
        ]),

        # FILA 2: Gráfica IPs y Radar (Puertos)
        html.Div(style=ROW_STYLE, children=[
            html.Div([
                html.H3("Top 10 Source IPs", style=font_style("1.2rem", "600", C_TEXT)),
                dcc.Graph(id="grafica_ips", config={"displayModeBar": False})
            ], style=GRAPH_CONTAINER_STYLE),

            html.Div([
                html.H3("Puertos Destino (Radar Polar)", style=font_style("1.2rem", "600", C_TEXT)),
                dcc.Graph(id="grafica_puertos", config={"displayModeBar": False})
            ], style=GRAPH_CONTAINER_STYLE),
        ]),

        # TABLA EVENTOS RECIENTES
        html.Div([
            html.H3(
                "Últimos Eventos de Red", 
                style={
                    **font_style("1.3rem", "600", C_TEXT),
                    "marginBottom": "35px"
                }
            ),            
            
            dash_table.DataTable(
                id="tabla_eventos",
                style_table={
                    "overflowX": "auto", 
                    "borderRadius": "8px", 
                    "border": f"1px solid {C_BORDER}"
                },
                style_header={
                    "backgroundColor": "#1A1A1A",
                    "color": "#FFFFFF",
                    "fontWeight": "bold",
                    "border": f"1px solid {C_BORDER}",
                    "textTransform": "uppercase",
                    "fontSize": "13px",
                    "padding": "12px",
                    "textAlign": "center"
                },
                style_cell={
                    "backgroundColor": "#121212",
                    "color": C_TEXT,
                    "textAlign": "center",
                    "padding": "12px",
                    "fontFamily": "Segoe UI, Arial",
                    "border": f"1px solid {C_BORDER}",
                    "fontSize": "14px"
                },
                style_data_conditional=[
                    {
                        "if": {"row_index": "odd"},
                        "backgroundColor": "#181818"
                    },
                    {
                        "if": {"filter_query": '{Prediccion_IA} != "BENIGN"'},
                        "backgroundColor": "#3A0000",
                        "color": "#FF6666",
                        "fontWeight": "bold",
                        "border": "1px solid #FF003C"
                    }
                ],
                page_size=10
            )
        ], style={"backgroundColor": C_PAPER, "padding": "25px", "borderRadius": "12px", "border": f"1px solid {C_BORDER}"})
    ]
)

def layout_base_animado(title_text=""):
    return dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=C_TEXT),
        margin=dict(l=40, r=40, t=30, b=40),
        uirevision='constant', 
        transition=dict(duration=500, easing="cubic-in-out")
    )

# CALLBACK: ACTUALIZA TODO EL DASHBOARD
@app.callback(
    [
        Output("kpi_total", "children"),
        Output("kpi_ips", "children"),
        Output("kpi_ataques", "children"),
        Output("kpi_departamentos", "children"),
        Output("grafica_predicciones", "figure"),
        Output("grafica_departamentos", "figure"),
        Output("grafica_ips", "figure"),
        Output("grafica_puertos", "figure"),
        Output("tabla_eventos", "data"),
        Output("tabla_eventos", "columns"),
        Output("hora_actualizacion", "children"),
        Output("store_ataque_ts", "data"),
        Output("warning_contenido", "children"),
    ],
    Input("interval", "n_intervals")
)

# Función para actualizar el dashboard cada 5 segundos
def actualizar_dashboard(_):
    try:
        df = pd.read_csv("datos_consolidados.csv", low_memory=False)

        # KPIs
        total_registros = f"{len(df):,}"
        total_ips = f"{df['Source IP'].nunique():,}"
        ataques_count = len(df[df["Prediccion_IA"].str.upper() != "BENIGN"])
        ataques = f"{ataques_count:,}"
        departamentos = f"{df['Departamento'].nunique():,}"

        # GRÁFICA PREDICCIONES
        pred = df["Prediccion_IA"].value_counts().reset_index()

        separacion = [0 if val == "BENIGN" else 0.1 for val in pred["Prediccion_IA"]]

        fig_pred = go.Figure(data=[go.Pie(
            labels=pred["Prediccion_IA"], 
            values=pred["count"], 
            pull=separacion, 
            marker=dict(colors=NEON_PALETTE, line=dict(color=C_PAPER, width=2)),
            textinfo='percent+label',
            hoverinfo='label+value'
        )])
        fig_pred.update_layout(**layout_base_animado(), showlegend=False, height=320)


        # GRÁFICA DEPARTAMENTOS
        dep = df["Departamento"].value_counts().sort_values(ascending=True).reset_index()
        
        colores_barras = (NEON_PALETTE * (len(dep) // len(NEON_PALETTE) + 1))[:len(dep)]

        fig_dep = go.Figure(data=[go.Bar(
            y=dep["Departamento"], 
            x=dep["count"], 
            orientation='h',
            marker=dict(
                color=colores_barras,
                line=dict(color=C_PAPER, width=1)
            )
        )])
        fig_dep.update_layout(**layout_base_animado(), height=320)
        fig_dep.update_xaxes(showgrid=True, gridcolor=C_BORDER)
        fig_dep.update_yaxes(showgrid=False)

        
        
        # GRÁFICA IPS 
        ips = df["Source IP"].value_counts().head(10).reset_index()
        
        colores_barras_ips = (NEON_PALETTE * (len(ips) // len(NEON_PALETTE) + 1))[:len(ips)]

        fig_ips = go.Figure(data=[go.Bar(
            x=ips["Source IP"], 
            y=ips["count"],
            text=ips["count"],
            textposition='outside',
            textfont=dict(color="#FFFFFF", size=12, weight="bold"),
            marker=dict(
                color=colores_barras_ips,
                line=dict(color=C_BORDER, width=1)
            ),
            hovertemplate="<b>IP: %{x}</b><br>Eventos: %{y}<extra></extra>"
        )])
        
        fig_ips.update_layout(**layout_base_animado())
        
        fig_ips.update_layout(
            height=320,
            margin=dict(t=30, l=40, r=40, b=40),
            xaxis=dict(showgrid=False, tickangle=-45, color=C_TEXT),
            yaxis=dict(
                showgrid=True, 
                gridcolor=C_BORDER, 
                title="Conexiones", 
                type='log'
            )
        )


        # GRÁFICA PUERTOS
        puertos = df["Destination Port"].astype(str).value_counts().head(10).reset_index()
        fig_ports = go.Figure(data=go.Barpolar(
            r=puertos["count"],
            theta=puertos["Destination Port"],
            marker_color=puertos["count"],
            marker_colorscale="Plasma",
            opacity=0.8
        ))
        fig_ports.update_layout(
            **layout_base_animado(),
            height=320,
            polar=dict(
                radialaxis=dict(showticklabels=False, gridcolor=C_BORDER),
                angularaxis=dict(gridcolor=C_BORDER, tickfont=dict(color=C_TEXT, size=11)),
                bgcolor='rgba(0,0,0,0)'
            )
        )


        # TABLA
        columnas_tabla = ["Fecha_Hora_Ataque", "Source IP", "Destination IP", "Destination Port", "Departamento", "Prediccion_IA"]
        columnas_tabla = [c for c in columnas_tabla if c in df.columns]
        tabla = df[columnas_tabla].tail(10)
        data = tabla.to_dict("records")
        columns = [{"name": i, "id": i} for i in tabla.columns]

        hora = datetime.now().strftime("Última actualización: %H:%M:%S")

        # ADVERTENCIAS
        warning_contenido = []
        nuevo_ts = None
        try:
            obj_bloqueo = s3.get_object(Bucket=bucket, Key="antecedentes/ips_bloqueadas.csv")
            df_bloqueo = pd.read_csv(io.BytesIO(obj_bloqueo["Body"].read()))

            if not df_bloqueo.empty:
                nuevo_ts = datetime.now().timestamp()
                
                for _, row in df_bloqueo.iterrows():
                    ip = row.get("ip_origen", "N/A")
                    df_ip = df[df["Source IP"] == ip]

                    eventos = len(df_ip)
                    if "Flow Duration" in df.columns and not df_ip.empty:
                        tiempo_ejec = f"{round(df_ip['Flow Duration'].astype(float).sum() / 1e6, 2)} s"
                    else:
                        tiempo_ejec = "N/A"

                    if "Fecha_Hora_Ataque" in df.columns and not df_ip.empty:
                        hora_ataque = str(df_ip["Fecha_Hora_Ataque"].iloc[-1])
                    else:
                        hora_ataque = "N/A"

                    warning_contenido.append(
                        html.Div([
                            html.Div([
                                svg_icon(PATH_BUG, color=C_DANGER, size=16, margin_right="8px"),
                                html.Span("IP Maliciosa: ", style={"color": "#ff9999", "fontWeight": "bold", "verticalAlign": "middle"}),
                                html.Span(str(ip), style={"color": "white", "verticalAlign": "middle"})
                            ]),
                            html.Div([
                                svg_icon(PATH_LAYER, color=C_DANGER, size=16, margin_right="8px"),
                                html.Span("Eventos: ", style={"color": "#ff9999", "fontWeight": "bold", "verticalAlign": "middle"}),
                                html.Span(str(eventos), style={"color": "white", "verticalAlign": "middle"})
                            ]),
                            html.Div([
                                svg_icon(PATH_STOPWATCH, color=C_DANGER, size=16, margin_right="8px"),
                                html.Span("Tiempo de Ejecución: ", style={"color": "#ff9999", "fontWeight": "bold", "verticalAlign": "middle"}),
                                html.Span(tiempo_ejec, style={"color": "white", "verticalAlign": "middle"})
                            ]),
                            html.Div([
                                svg_icon(PATH_CLOCK, color=C_DANGER, size=16, margin_right="8px"),
                                html.Span("Hora del Ataque: ", style={"color": "#ff9999", "fontWeight": "bold", "verticalAlign": "middle"}),
                                html.Span(hora_ataque, style={"color": "white", "verticalAlign": "middle"})
                            ])
                        ], style={
                            "display": "flex", 
                            "flexWrap": "wrap", 
                            "gap": "20px", 
                            "padding": "12px 0", 
                            "borderBottom": "1px solid #5a0000"
                        })
                    )
        except Exception:
            pass

        return (total_registros, total_ips, ataques, departamentos, fig_pred, fig_dep, fig_ips, fig_ports, data, columns, hora, nuevo_ts, warning_contenido)

    except Exception as e:
        print("Error:", e)
        fig_vacio = go.Figure().add_annotation(text="Esperando datos...", showarrow=False, font=dict(size=20, color=C_TEXT_MUTED))
        fig_vacio.update_layout(**layout_base_animado())
        return ("0", "0", "0", "0", fig_vacio, fig_vacio, fig_vacio, fig_vacio, [], [], "Esperando datos...", None, [])


# CALLBACK WARNING
@app.callback(
    [Output("warning_banner", "style"), Output("warning_countdown", "children")],
    [Input("interval_warning", "n_intervals"), Input("store_ataque_ts", "data")]
)
def controlar_warning(_, ataque_ts):
    if ataque_ts is None:
        return WARNING_STYLE_HIDDEN, ""
    segundos_restantes = 30 - int(datetime.now().timestamp() - ataque_ts)
    if segundos_restantes <= 0:
        return WARNING_STYLE_HIDDEN, ""
    return WARNING_STYLE_VISIBLE, f"Se cierra en {segundos_restantes}s"

if __name__ == "__main__":
    app.run(debug=True)