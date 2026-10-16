from typing import Dict, List, Set, Tuple
from models import ClockNode, WireModel, BufferType

class CTSValidator:
    """
    Модуль верификации дерева синхронизации.
    Проверяет корректность графа, физические ограничения и тайминги.
    """
    def __init__(
        self, 
        max_fanout: int, 
        max_depth: int, 
        chip_width: float, 
        chip_height: float, 
        available_buffers: Dict[str, BufferType]
    ):
        self.max_fanout = max_fanout
        self.max_depth = max_depth
        self.chip_width = chip_width
        self.chip_height = chip_height
        self.available_buffers = available_buffers
        
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, root: ClockNode, expected_sinks_count: int, sink_delays: Dict[str, float]) -> Tuple[bool, List[str], List[str]]:
        self.errors.clear()
        self.warnings.clear()

        if not root:
            self.errors.append("Дерево синхронизации пустое (отсутствует корень).")
            return False, self.errors, self.warnings

        visited_nodes: Set[str] = set()
        connected_sinks: Set[str] = set()

        self._traverse_and_verify(root, visited_nodes, connected_sinks, current_depth=1)

        if len(connected_sinks) != expected_sinks_count:
            self.errors.append(
                f"Нарушена связность! Подключено sink'ов: {len(connected_sinks)} из ожидаемых {expected_sinks_count}."
            )

        return len(self.errors) == 0, self.errors, self.warnings

    def _traverse_and_verify(self, node: ClockNode, visited: Set[str], connected_sinks: Set[str], current_depth: int):
        if node.id in visited:
            self.errors.append(f"Обнаружен цикл в дереве! Узел '{node.id}' посещен повторно.")
            return
        visited.add(node.id)

        if not (0 <= node.x <= self.chip_width) or not (0 <= node.y <= self.chip_height):
            self.errors.append(
                f"Узел '{node.id}' ({node.node_type}) вышел за границы кристалла: ({node.x}, {node.y})."
            )

        if current_depth > self.max_depth:
            self.errors.append(
                f"Превышена максимальная глубина дерева! Узел '{node.id}' находится на уровне {current_depth} (max: {self.max_depth})."
            )

        if len(node.children) > self.max_fanout:
            self.errors.append(
                f"Превышено максимальное ветвление (fanout) для узла '{node.id}': "
                f"потомков {len(node.children)} (max: {self.max_fanout})."
            )

        if node.node_type == "buffer":
            if not node.buffer_ref:
                self.errors.append(f"Узел '{node.id}' заявлен как буфер, но не имеет ссылки на параметры BufferType.")
            elif node.buffer_ref.id not in self.available_buffers:
                self.errors.append(
                    f"Буфер '{node.id}' использует недоступный или отсутствующий в библиотеке тип '{node.buffer_ref.id}'."
                )

        if node.node_type == "sink" and node.sink_ref:
            connected_sinks.add(node.sink_ref.id)
            if node.delay_from_source > node.sink_ref.required_arrival_time:
                self.warnings.append(
                    f"Нарушение таймингов на '{node.sink_ref.id}': "
                    f"задержка {node.delay_from_source:.3f} > требуется {node.sink_ref.required_arrival_time}."
                )

        for child in node.children:
            if child.parent != node:
                self.errors.append(f"Нарушена иерархическая структура! Узел '{child.id}' указывает на неверного родителя.")
            self._traverse_and_verify(child, visited, connected_sinks, current_depth + 1)
