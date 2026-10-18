import math
from typing import Dict, List, Tuple
from models import ClockNode, WireModel, BufferType

def get_manhattan_dist(n1: ClockNode, n2: ClockNode) -> float:
    """Вычисляет Манхэттенское расстояние между узлами (физическая трассировка)"""
    return abs(n1.x - n2.x) + abs(n1.y - n2.y)

class DelayCalculator:
    """
    Универсальный модуль расчета временных характеристик дерева синхронизации.
    Приводит вычисления к реальным физическим величинам нанометрового техпроцесса:
    Длина -> Микроны (мкм), Сопротивление -> Омы (Ом), Емкость -> Пикофарады (пФ).
    Итоговая задержка рассчитывается строго в наносекундах (нс).
    """
    def __init__(self, wire_model: WireModel):
        self.wire_model = wire_model
        self.model_type = wire_model.model.lower()
        # Извлекаем масштаб перевода координат в микроны (мкм)
        self.scale = float(getattr(wire_model, 'unit_length', 1.0))
        
        # Коэффициент масштабирования емкости: из фемтофарад (фФ) в пикофарады (пФ)
        # 1 фФ = 1e-3 пФ. Необходим, чтобы Ohm * pF давал наносекунды (ns).
        self.FF_TO_PF = 1e-3

    def calculate(self, root: ClockNode) -> Tuple[Dict[str, float], float]:
        """
        Основной метод расчета. Считает задержки для всего дерева.
        Возвращает:
            - Словарь {id_sink: delay} в наносекундах
            - Значение разброса (Skew) в наносекундах
        """
        # Шаг 1: Обход снизу вверх — сбор емкостей поддеревьев (в фФ)
        self._update_capacitance_bottom_up(root)
        
        # Шаг 2: Обход сверху вниз — распространение задержек с переводом фФ -> пФ
        root.delay_from_source = 0.0
        sink_delays: Dict[str, float] = {}
        self._compute_delay_top_down(root, sink_delays)
        
        # Шаг 3: Вычисление Skew (разброса задержек)
        if not sink_delays:
            return {}, 0.0
        
        delays = list(sink_delays.values())
        skew = max(delays) - min(delays)
        
        return sink_delays, skew

    def _update_capacitance_bottom_up(self, node: ClockNode) -> float:
        """
        Первый проход: вычисляет электрическую нагрузку поддерева (в фемтофарадах, фФ).
        Переводит геометрические расстояния в реальные микроны через unit_length.
        """
        if node.node_type == "sink" and node.sink_ref:
            # Емкость терминала (уже в фФ по ТЗ)
            node.downstream_capacitance = node.sink_ref.capacitance
            return node.downstream_capacitance
        
        if node.node_type == "buffer" and node.buffer_ref:
            # Предыдущий уровень видит только входную емкость этого буфера (в фФ)
            node.downstream_capacitance = node.buffer_ref.input_capacitance
            # Сбор выходной емкости поддерева для этого буфера
            self._update_buffer_subtree_capacitance(node)
            return node.downstream_capacitance

        # Для точек ветвления (branch) и корня (source) собираем емкости детей и проводов
        total_cap = 0.0
        for child in node.children:
            raw_dist = get_manhattan_dist(node, child)
            # Переводим абстрактную длину провода в физические микроны (мкм)
            child.wire_length_to_parent = raw_dist * self.scale
            
            # Емкость провода: длина (мкм) * unit_capacitance (фФ/мкм) -> получаем фФ
            wire_cap = child.wire_length_to_parent * self.wire_model.unit_capacitance
            child_cap = self._update_capacitance_bottom_up(child)
            
            total_cap += wire_cap + child_cap
            
        node.downstream_capacitance = total_cap
        return total_cap

    def _update_buffer_subtree_capacitance(self, buffer_node: ClockNode):
        """Вспомогательный метод сбора емкостей нагрузки на выходе буфера (в фФ)"""
        total_cap = 0.0
        for child in buffer_node.children:
            raw_dist = get_manhattan_dist(buffer_node, child)
            # Переводим длину в микроны (мкм)
            child.wire_length_to_parent = raw_dist * self.scale
            
            # Длина (мкм) * unit_capacitance (фФ/мкм) -> фФ
            wire_cap = child.wire_length_to_parent * self.wire_model.unit_capacitance
            child_cap = self._update_capacitance_bottom_up(child)
            total_cap += wire_cap + child_cap
            
        buffer_node.buffer_output_load = total_cap

    def _compute_delay_top_down(self, node: ClockNode, sink_delays: Dict[str, float]):
        """
        Второй проход: рассчитывает задержку (в нс), переводя емкости из фФ в пФ.
        """
        for child in node.children:
            # 1. Параметры драйвера
            intrinsic_delay = 0.0 # В наносекундах (нс)
            r_driver = 0.0        # В Омах (Ом)
            
            if node.node_type == "buffer" and node.buffer_ref:
                intrinsic_delay = node.buffer_ref.intrinsic_delay
                r_driver = node.buffer_ref.output_resistance
            
            # 2. Физические параметры провода (длина l_wire уже в мкм)
            l_wire = child.wire_length_to_parent
            r_wire = l_wire * self.wire_model.unit_resistance  # мкм * Ом/мкм -> Ом
            
            # ИЗМЕНЕНО: Конвертируем емкость провода из фФ в пФ для формулы Элмора
            c_wire = (l_wire * self.wire_model.unit_capacitance) * self.FF_TO_PF
            
            # ИЗМЕНЕНО: Конвертируем емкости нагрузок из фФ в пФ
            c_load = child.downstream_capacitance * self.FF_TO_PF
            
            # Определение суммарной выходной емкости драйвера каскада (перевод фФ -> пФ)
            raw_driver_load = node.buffer_output_load if node.node_type == "buffer" else node.downstream_capacitance
            total_driver_load = raw_driver_load * self.FF_TO_PF

            # 3. Расчет задержки сегмента (компоненты: нс + Ом * пФ + Ом * пФ -> нс)
            if self.model_type == "elmore":
                segment_delay = (
                    intrinsic_delay + 
                    r_driver * total_driver_load + 
                    r_wire * (0.5 * c_wire + c_load)
                )
            else:
                # В линейной модели коэффициент переводится с учетом физических микронов
                segment_delay = (
                    intrinsic_delay + 
                    r_driver * total_driver_load + 
                    l_wire * 0.001  # Эвристическая линейная задержка: 1 пс (0.001 нс) на микрон
                )
            
            child.delay_from_source = node.delay_from_source + segment_delay
            
            if child.node_type == "sink" and child.sink_ref:
                sink_delays[child.sink_ref.id] = child.delay_from_source
                
            self._compute_delay_top_down(child, sink_delays)
