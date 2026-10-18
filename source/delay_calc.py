import math
from typing import Dict, List, Tuple
from models import ClockNode, WireModel, BufferType

def get_manhattan_dist(n1: ClockNode, n2: ClockNode) -> float:
    """Вычисляет Манхэттенское расстояние между узлами (физическая трассировка)"""
    return abs(n1.x - n2.x) + abs(n1.y - n2.y)

class DelayCalculator:
    """
    Универсальный модуль расчета временных характеристик дерева синхронизации.
    Поддерживает модели задержки Elmore и Linear с обязательным учетом масштаба unit_length.
    """
    def __init__(self, wire_model: WireModel):
        self.wire_model = wire_model
        self.model_type = wire_model.model.lower()
        # Извлекаем масштаб перевода координат в физические единицы длины (по умолчанию 1.0)
        self.scale = float(getattr(wire_model, 'unit_length', 1.0))

    def calculate(self, root: ClockNode) -> Tuple[Dict[str, float], float]:
        """
        Основной метод расчета. Считает задержки для всего дерева.
        Возвращает:
            - Словарь {id_sink: delay}
            - Значение разброса (Skew)
        """
        # Шаг 1: Обход снизу вверх — сбор емкостей поддеревьев (Downstream Capacitance)
        self._update_capacitance_bottom_up(root)
        
        # Шаг 2: Обход сверху вниз — распространение задержек
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
        Первый проход: вычисляет электрическую нагрузку, которую видит каждый узел.
        Включает масштабирование длины проводов через unit_length.
        """
        if node.node_type == "sink" and node.sink_ref:
            node.downstream_capacitance = node.sink_ref.capacitance
            return node.downstream_capacitance
        
        if node.node_type == "buffer" and node.buffer_ref:
            # Предыдущий уровень видит только входную емкость этого буфера
            node.downstream_capacitance = node.buffer_ref.input_capacitance
            # Сбор емкостей детей с учетом физического масштаба
            self._update_buffer_subtree_capacitance(node)
            return node.downstream_capacitance

        # Для точек ветвления (branch) и корня (source) собираем емкости детей и проводов
        total_cap = 0.0
        for child in node.children:
            # ИЗМЕНЕНО: Вычисляем абстрактную длину и сразу масштабируем её через unit_length
            raw_dist = get_manhattan_dist(node, child)
            child.wire_length_to_parent = raw_dist * self.scale
            
            # Емкость провода рассчитывается от отмасштабированной длины
            wire_cap = child.wire_length_to_parent * self.wire_model.unit_capacitance
            child_cap = self._update_capacitance_bottom_up(child)
            
            total_cap += wire_cap + child_cap
            
        node.downstream_capacitance = total_cap
        return total_cap

    def _update_buffer_subtree_capacitance(self, buffer_node: ClockNode):
        """Вспомогательный метод для сбора емкостей внутри поддерева буфера с учетом масштаба"""
        total_cap = 0.0
        for child in buffer_node.children:
            # ИЗМЕНЕНО: Применяем unit_length при расчете длины сегмента
            raw_dist = get_manhattan_dist(buffer_node, child)
            child.wire_length_to_parent = raw_dist * self.scale
            
            wire_cap = child.wire_length_to_parent * self.wire_model.unit_capacitance
            child_cap = self._update_capacitance_bottom_up(child)
            total_cap += wire_cap + child_cap
            
        buffer_node.buffer_output_load = total_cap

    def _compute_delay_top_down(self, node: ClockNode, sink_delays: Dict[str, float]):
        """
        Второй проход: рассчитывает накопленную задержку от источника до каждого узла.
        """
        for child in node.children:
            # 1. Определяем параметры драйвера (текущего узла)
            intrinsic_delay = 0.0
            r_driver = 0.0
            
            if node.node_type == "buffer" and node.buffer_ref:
                intrinsic_delay = node.buffer_ref.intrinsic_delay
                r_driver = node.buffer_ref.output_resistance
            
            # 2. Физические параметры линии связи (длина l_wire уже отмасштабирована на Шаге 1)
            l_wire = child.wire_length_to_parent
            r_wire = l_wire * self.wire_model.unit_resistance
            c_wire = l_wire * self.wire_model.unit_capacitance
            
            # Нагрузка на конце провода
            c_load = child.downstream_capacitance 
            total_driver_load = node.buffer_output_load if node.node_type == "buffer" else node.downstream_capacitance

            # 3. Расчет задержки сегмента с учетом физического размера
            if self.model_type == "elmore":
                # Модель Элмора: r_wire и c_wire базируются на верном масштабе
                segment_delay = (
                    intrinsic_delay + 
                    r_driver * total_driver_load + 
                    r_wire * (0.5 * c_wire + c_load)
                )
            else:
                # Линейная модель: задержка пропорциональна отмасштабированной длине провода
                segment_delay = (
                    intrinsic_delay + 
                    r_driver * total_driver_load + 
                    l_wire * 0.1  # Базовый коэффициент задержки на единицу физической длины
                )
            
            child.delay_from_source = node.delay_from_source + segment_delay
            
            # Если дошли до sink — сохраняем результат
            if child.node_type == "sink" and child.sink_ref:
                sink_delays[child.sink_ref.id] = child.delay_from_source
                
            # Рекурсивно идем дальше вниз по дереву
            self._compute_delay_top_down(child, sink_delays)
