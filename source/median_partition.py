import math
from typing import List, Dict, Any, Tuple, Optional
from models import ClockNode, ClockSource, Sink, BufferType, WireModel

class MedianPartitionCTS:
    """
    Класс синтеза дерева синхронизации на основе алгоритма медианного разбиения.
    """
    def __init__(
        self, 
        clock_source: ClockSource, 
        sinks: List[Sink], 
        buffers: Dict[str, BufferType], 
        tree_params: Dict[str, Any]
    ):
        self.clock_source = clock_source
        self.sinks = sinks
        self.buffers = buffers
        self.params = tree_params
        
        # Извлечение параметров алгоритма с дефолтными значениями
        self.max_fanout = int(self.params.get("max_fanout", 4))
        self.min_sinks = int(self.params.get("min_sinks_for_partition", 2))
        self.criterion = self.params.get("partition_criterion", "balanced_capacitance")
        self.axis_mode = self.params.get("partition_axis", "auto")
        self.median_type = self.params.get("median_type", "geometric_median")
        self.buffer_insertion = self.params.get("buffer_insertion", True)
        self.buffer_selection = self.params.get("buffer_selection", "size_by_load")
        
        # Выбираем буфер по умолчанию (наименьший доступный)
        self.default_buffer = min(buffers.values(), key=lambda b: b.drive_strength) if buffers else None
        
        self.node_counter = 0

    def _next_node_id(self, prefix: str) -> str:
        """Генерирует уникальный ID для новых узлов дерева"""
        self.node_counter += 1
        return f"{prefix}_{self.node_counter}"

    def build_tree(self) -> ClockNode:
        """
        Запускает CTS и возвращает корень дерева (ClockNode).
        """
        # Создаем корень дерева на позиции источника синхронизации
        root = ClockNode(
            id=self.clock_source.id,
            x=self.clock_source.x,
            y=self.clock_source.y,
            node_type="source"
        )
        
        # Если sinks нет, возвращаем пустой корень
        if not self.sinks:
            return root
            
        # Запуск рекурсивного построения поддерева
        self._partition_recursive(root, self.sinks, depth=1)
        return root

    def _partition_recursive(self, parent_node: ClockNode, current_sinks: List[Sink], depth: int):
        """
        Рекурсивный шаг разбиения множества sink'ов.
        """
        # Базовый случай: если элементов меньше или равно макс. ветвлению (fanout),
        # подключаем их напрямую к текущему родителю
        if len(current_sinks) <= self.max_fanout:
            for sk in current_sinks:
                sink_node = ClockNode(
                    id=sk.id, x=sk.x, y=sk.y, 
                    node_type="sink", sink_ref=sk
                )
                parent_node.add_child(sink_node)
            return

        # 1. Определяем ось разбиения (X или Y)
        axis = self._choose_axis(current_sinks, depth)
        
        # 2. Сортируем элементы вдоль выбранной оси
        if axis == 'x':
            current_sinks.sort(key=lambda s: s.x)
        else:
            current_sinks.sort(key=lambda s: s.y)

        # 3. Делим sink'и на группы (k-way разбиение в зависимости от max_fanout, обычно бинарное k=2)
        # Для классического медианного разбиения делим пополам (на 2 подгруппы)
        mid_idx = self._find_median_index(current_sinks)
        groups = [current_sinks[:mid_idx], current_sinks[mid_idx:]]
        
        # 4. Вычисляем физические координаты точки ветвления (медианы) для текущего уровня
        branch_x, branch_y = self._calculate_median_position(current_sinks)
        
        # Создаем промежуточный узел (Branch или Buffer)
        node_type = "buffer" if self.buffer_insertion else "branch"
        branch_node = ClockNode(
            id=self._next_node_id("BUF" if node_type == "buffer" else "BR"),
            x=branch_x, y=branch_y,
            node_type=node_type
        )
        
        # Назначаем тип буфера, если вставка включена
        if node_type == "buffer" and self.default_buffer:
            branch_node.buffer_ref = self._select_buffer_for_group(current_sinks)

        # Соединяем родителя с этой новой точкой ветвления
        parent_node.add_child(branch_node)

        # 5. Рекурсивно спускаемся в каждую подгруппу
        for group in groups:
            if group:
                self._partition_recursive(branch_node, group, depth + 1)

    def _choose_axis(self, sinks: List[Sink], depth: int) -> str:
        """Определяет ось разреза на основе конфигурации"""
        if self.axis_mode == "x":
            return "x"
        if self.axis_mode == "y":
            return "y"
        if self.axis_mode == "alternate":
            return "x" if depth % 2 != 0 else "y"
            
        # Режим "auto": режем по оси с наибольшим разбросом (длиной охватывающего прямоугольника)
        xs = [s.x for s in sinks]
        ys = [s.y for s in sinks]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        return "x" if dx >= dy else "y"

    def _find_median_index(self, sorted_sinks: List[Sink]) -> int:
        """
        Находит индекс для разделения группы согласно критерию из ТЗ.
        """
        if self.criterion == "balanced_count":
            # Простая геометрическая медиана: делим поровну по количеству
            return len(sorted_sinks) // 2
            
        # По умолчанию: "balanced_capacitance" — балансировка по суммарной емкости
        total_cap = sum(s.capacitance for s in sorted_sinks)
        accumulated_cap = 0.0
        for i, s in enumerate(sorted_sinks):
            accumulated_cap += s.capacitance
            if accumulated_cap >= total_cap / 2.0:
                # Гарантируем, что индекс не выйдет за границы и не создаст пустую группу
                return max(1, i)
        return len(sorted_sinks) // 2

    def _calculate_median_position(self, sinks: List[Sink]) -> Tuple[float, float]:
        """
        Вычисляет координаты виртуального центра (точки ветвления).
        """
        if self.median_type == "centroid":
            # Центр масс, взвешенный по емкости
            total_cap = sum(s.capacitance for s in sinks)
            if total_cap == 0:
                return sinks[0].x, sinks[0].y
            cx = sum(s.x * s.capacitance for s in sinks) / total_cap
            cy = sum(s.y * s.capacitance for s in sinks) / total_cap
            return cx, cy

        # По умолчанию/Манхэттенская медиана: берем среднее значение координат средних элементов
        xs = sorted([s.x for s in sinks])
        ys = sorted([s.y for s in sinks])
        mx = xs[len(xs) // 2]
        my = ys[len(ys) // 2]
        return mx, my

    def _select_buffer_for_group(self, sinks: List[Sink]) -> BufferType:
        """
        Стратегия выбора буфера по нагрузке (size_by_load).
        Чем больше суммарная емкость группы, тем мощнее берется буфер.
        """
        if self.buffer_selection == "uniform" or not self.buffers:
            return self.default_buffer
            
        total_cap = sum(s.capacitance for s in sinks)
        
        # Эвристика: выбираем буфер, чья нагрузочная способность соответствует емкости
        # Сортируем буферы по возрастанию силы драйвера
        sorted_bufs = sorted(self.buffers.values(), key=lambda b: b.drive_strength)
        
        if total_cap < 15.0:
            return sorted_bufs[0]  # STD
        elif total_cap < 30.0 and len(sorted_bufs) > 1:
            return sorted_bufs[1]  # MID
        else:
            return sorted_bufs[-1] # LARGE
