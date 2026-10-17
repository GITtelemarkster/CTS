import math
from typing import List, Dict, Any, Tuple, Optional
from models import ClockNode, ClockSource, Sink, BufferType, WireModel

class MedianPartitionCTS:
    """
    Класс синтеза дерева синхронизации на основе классического бинарного алгоритма медианного разбиения.
    """
    def __init__(
        self, 
        clock_source: ClockSource, 
        sinks: List[Sink], 
        buffers: Dict[str, BufferType], 
        wire_model: WireModel,  # ИЗМЕНЕНО: Добавили аргумент в конструктор
        tree_params: Dict[str, Any]
    ):
        self.clock_source = clock_source
        self.sinks = sinks
        self.buffers = buffers
        self.wire_model = wire_model  # ИЗМЕНЕНО: Сохраняем в атрибуты класса
        self.params = tree_params
        
        self.max_fanout = int(self.params.get("max_fanout", 4))
        self.min_sinks = int(self.params.get("min_sinks_for_partition", 2))
        self.criterion = self.params.get("partition_criterion", "balanced_capacitance")
        self.axis_mode = self.params.get("partition_axis", "auto")
        self.median_type = self.params.get("median_type", "geometric_median")
        self.buffer_insertion = self.params.get("buffer_insertion", True)
        self.buffer_selection = self.params.get("buffer_selection", "size_by_load")
        
        self.default_buffer = min(buffers.values(), key=lambda b: b.drive_strength) if buffers else None
        self.node_counter = 0

    def _next_node_id(self, prefix: str) -> str:
        self.node_counter += 1
        return f"{prefix}_{self.node_counter}"

    def build_tree(self) -> ClockNode:
        root = ClockNode(
            id=self.clock_source.id,
            x=self.clock_source.x,
            y=self.clock_source.y,
            node_type="source"
        )
        if not self.sinks:
            return root
            
        # Запускаем разбиение от корня
        self._partition_recursive(root, self.sinks, depth=1)
        return root

    def _partition_recursive(self, parent_node: ClockNode, current_sinks: List[Sink], depth: int):
        # Базовый случай: если элементов укладывается в max_fanout, цепляем их напрямую
        if len(current_sinks) <= self.max_fanout:
            for sk in current_sinks:
                sink_node = ClockNode(
                    id=sk.id, x=sk.x, y=sk.y, 
                    node_type="sink", sink_ref=sk
                )
                parent_node.add_child(sink_node)
            return

        # 1. Выбираем ось и сортируем
        axis = self._choose_axis(current_sinks, depth)
        if axis == 'x':
            current_sinks.sort(key=lambda s: s.x)
        else:
            current_sinks.sort(key=lambda s: s.y)

        # 2. ИЗМЕНЕНО: Строго бинарное деление на 2 подгруппы для классического алгоритма
        groups = self._split_into_k_groups(current_sinks, k=2)

        # 3. Для каждой подгруппы создаем свой дочерний буфер/точку ветвления
        for group in groups:
            if not group:
                continue
                
            branch_x, branch_y = self._calculate_median_position(group)
            node_type = "buffer" if self.buffer_insertion else "branch"
            
            child_node = ClockNode(
                id=self._next_node_id("BUF" if node_type == "buffer" else "BR"),
                x=branch_x, y=branch_y,
                node_type=node_type
            )
            
            if node_type == "buffer" and self.default_buffer:
                child_node.buffer_ref = self._select_buffer_for_group(group)

            # Подключаем к родителю (в бинарном режиме у промежуточного узла будет строго 2 потомка)
            parent_node.add_child(child_node)

            # Рекурсивно уходим вниз
            self._partition_recursive(child_node, group, depth + 1)

    def _choose_axis(self, sinks: List[Sink], depth: int) -> str:
        if self.axis_mode == "x": return "x"
        if self.axis_mode == "y": return "y"
        if self.axis_mode == "alternate": return "x" if depth % 2 != 0 else "y"
            
        xs = [s.x for s in sinks]
        ys = [s.y for s in sinks]
        return "x" if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else "y"

    def _split_into_k_groups(self, sorted_sinks: List[Sink], k: int = 2) -> List[List[Sink]]:
        """
        ИЗМЕНЕНО: Разбивает массив строго на 2 сбалансированные группы по количеству или емкости.
        Параметр k игнорируется для обеспечения строго бинарного разбиения.
        """
        n = len(sorted_sinks)
        if n < 2:
            return [sorted_sinks, []]

        # Классическое бинарное разбиение по количеству (Strict Midpoint)
        if self.criterion == "balanced_count":
            mid = n // 2
            return [sorted_sinks[:mid], sorted_sinks[mid:]]

        # Бинарное разбиение по емкости (Balanced Capacitance)
        total_cap = sum(s.capacitance for s in sorted_sinks)
        target_half = total_cap / 2.0
        
        accumulated_cap = 0.0
        split_index = 0
        
        for i, s in enumerate(sorted_sinks):
            accumulated_cap += s.capacitance
            if accumulated_cap >= target_half:
                # Проверяем, какая точка деления ближе к идеальной половине: текущая или предыдущая
                prev_error = abs((accumulated_cap - s.capacitance) - target_half)
                curr_error = abs(accumulated_cap - target_half)
                
                if prev_error < curr_error and i > 0:
                    split_index = i
                else:
                    split_index = i + 1
                break
        
        # Гарантируем отсутствие пустых групп в крайних случаях
        if split_index == 0: 
            split_index = 1
        elif split_index == n: 
            split_index = n - 1

        return [sorted_sinks[:split_index], sorted_sinks[split_index:]]

    def _calculate_median_position(self, sinks: List[Sink]) -> Tuple[float, float]:
        if self.median_type == "centroid":
            total_cap = sum(s.capacitance for s in sinks)
            if total_cap == 0:
                return sinks[0].x, sinks[0].y
            cx = sum(s.x * s.capacitance for s in sinks) / total_cap
            cy = sum(s.y * s.capacitance for s in sinks) / total_cap
            return cx, cy

        xs = sorted([s.x for s in sinks])
        ys = sorted([s.y for s in sinks])
        return xs[len(xs) // 2], ys[len(ys) // 2]

    def _select_buffer_for_group(self, sinks: List[Sink]) -> BufferType:
        if self.buffer_selection == "uniform" or not self.buffers:
            return self.default_buffer
            
        # Считаем емкость потребителей
        sinks_cap = sum(s.capacitance for s in sinks)
        
        # Оценка емкости проводов: берем примерный периметр зоны, занимаемой sinks
        if len(sinks) > 1:
            xs = [s.x for s in sinks]
            ys = [s.y for s in sinks]
            estimated_wire_len = (max(xs) - min(xs)) + (max(ys) - min(ys))
            wire_cap = estimated_wire_len * self.wire_model.unit_capacitance
        else:
            wire_cap = 0.0
            
        total_cap = sinks_cap + wire_cap
        sorted_bufs = sorted(self.buffers.values(), key=lambda b: b.drive_strength)
        
        # Динамический выбор: самый мощный буфер для тяжелой нагрузки
        if total_cap < 15.0:
            return sorted_bufs[0]
        elif total_cap < 35.0 and len(sorted_bufs) > 1:
            return sorted_bufs[1]
        else:
            return sorted_bufs[-1]  # Самый мощный буфер из библиотеки

