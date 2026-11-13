"""Pruebas de integración: los dos patrones juntos en los flujos de Banco Senior+."""

import unittest
from datetime import datetime, timedelta
from pathlib import Path

from banco_senior import traza
from banco_senior.pension import HistorialConsignaciones
from banco_senior.sistema import armar_desde_csv, referencias_directas_entre_modulos

DATOS = Path(__file__).resolve().parent.parent / "datos"
NOVIEMBRE = DATOS / "pagos_2026-11.csv"
DICIEMBRE = DATOS / "pagos_2026-12.csv"


def setUpModule():
    traza.ACTIVA = False


def tearDownModule():
    traza.ACTIVA = True


class PruebasFlujo(unittest.TestCase):

    def setUp(self):
        # Jorge (3001110002) tiene el celular caído en todas las pruebas.
        self.sistema = armar_desde_csv(
            DATOS / "pensionados.csv", fallar_para={"3001110002"}
        )

    def avisos(self, documento):
        return [
            r
            for r in self.sistema.auditoria.registros
            if r.documento == documento and r.tipo.startswith("Aviso")
        ]

    # --- Día de pago (US-201, US-301, RNF-006) -------------------------------

    def test_dia_de_pago_abona_lo_que_concilia_y_reporta_diferencias(self):
        resultado = self.sistema.procesador.procesar(NOVIEMBRE)
        self.assertEqual(len(resultado.abonos), 4)
        self.assertEqual([f["documento"] for f in resultado.diferencias], ["1009999"])
        self.assertEqual(self.sistema.core.saldo("4001-0001"), 1423500)

    def test_cada_aviso_sale_por_el_canal_preferido(self):
        self.sistema.procesador.procesar(NOVIEMBRE)
        canales = {
            destino: canal for _, canal, destino, _ in self.sistema.operador.enviados
        }
        self.assertEqual(
            canales,
            {
                "3001110001": "sms",  # Rosa
                "carmen.rios@correo.test": "correo",  # Carmen
                "3001110004": "llamada",  # Luis
            },
        )

    def test_un_aviso_fallido_no_revierte_el_abono_y_queda_auditado(self):
        self.sistema.procesador.procesar(NOVIEMBRE)
        self.assertEqual(self.sistema.core.saldo("4001-0002"), 2150000)
        self.assertEqual([r.tipo for r in self.avisos("1001002")], ["Aviso FALLIDO"])

    def test_auditoria_registra_cada_abono(self):
        self.sistema.procesador.procesar(NOVIEMBRE)
        abonos = [
            r for r in self.sistema.auditoria.registros if r.tipo == "AbonoRegistrado"
        ]
        self.assertEqual(len(abonos), 4)

    def test_el_aviso_del_abono_sale_en_menos_de_5_minutos(self):
        resultado = self.sistema.procesador.procesar(NOVIEMBRE)
        abono_rosa = resultado.abonos[0]
        envio_rosa = next(
            m for m, _, d, _ in self.sistema.operador.enviados if d == "3001110001"
        )
        self.assertLess(envio_rosa - abono_rosa.momento, timedelta(minutes=5))

    def test_un_archivo_ya_procesado_no_se_abona_dos_veces(self):
        self.sistema.procesador.procesar(NOVIEMBRE)
        repetido = self.sistema.procesador.procesar(NOVIEMBRE)
        self.assertTrue(repetido.repetido)
        self.assertEqual(self.sistema.core.saldo("4001-0001"), 1423500)

    # --- Seguridad (US-303, US-108) -----------------------------------------

    def test_el_cuarto_intento_fallido_alerta_por_dos_canales(self):
        for _ in range(4):
            self.sistema.gestion.intento_fallido("1001004")
        canales = [canal for _, canal, _, _ in self.sistema.operador.enviados]
        self.assertEqual(canales, ["llamada", "correo"])

    def test_el_quinto_intento_fallido_bloquea_y_avisa(self):
        for _ in range(5):
            self.sistema.gestion.intento_fallido("1001004")
        self.assertIsNotNone(self.sistema.gestion.bloqueada_hasta("1001004"))
        tipos = [r.tipo for r in self.sistema.auditoria.registros]
        self.assertIn("CuentaBloqueada", tipos)
        self.assertIn("bloqueada", self.sistema.operador.enviados[-1][3])

    def test_intentos_espaciados_no_generan_alerta_de_acceso_sospechoso(self):
        inicio = datetime.now()
        for minuto in (
            0,
            2,
            4,
            6,
        ):  # el cuarto intento ya está fuera de la ventana de 5 minutos
            self.sistema.gestion.intento_fallido(
                "1001004", inicio + timedelta(minutes=minuto)
            )
        tipos = [r.tipo for r in self.sistema.auditoria.registros]
        self.assertNotIn("AccesoSospechoso", tipos)

    # --- Escalabilidad del Observer (US-203) --------------------------------

    def test_el_historial_se_agrega_sin_modificar_el_procesador(self):
        historial = HistorialConsignaciones()
        self.sistema.publicador.suscribir(historial)
        self.sistema.procesador.procesar(NOVIEMBRE)
        self.sistema.procesador.procesar(DICIEMBRE)
        periodos = [c.periodo for c in historial.consultar("1001001")]
        self.assertEqual(periodos, ["2026-12", "2026-11"])  # orden descendente

    # --- Desacoplamiento ------------------------------------------------------

    def test_no_hay_referencias_directas_entre_modulos(self):
        self.assertEqual(referencias_directas_entre_modulos(self.sistema), [])


if __name__ == "__main__":
    unittest.main()
