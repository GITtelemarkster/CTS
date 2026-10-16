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
            
        self._partition_recursive(root, self.sinks, depth=1)
        return root

    def _partition_recursive(self, parent_node: ClockNode, current_sinks: List[Sink], depth: int):
        if len(current_sinks) <= self.max_fanout:
            for sk in current_sinks:
                sink_node = ClockNode(
                    id=sk.id, x=sk.x, y=sk.y, 
                    node_type="sink", sink_ref=sk
                )
                parent_node.add_child(sink_node)
            return

        axis = self._choose_axis(current_sinks, depth)
        if axis == 'x':
            current_sinks.sort(key=lambda s: s.x)
        else:
            current_sinks.sort(key=lambda s: s.y)

        # Делим на K сбалансированных групп (K <= max_fanout)
        k = min(self.max_fanout, len(current_sinks))
        groups = self._split_into_k_groups(current_sinks, k)

        for group in groups:
            if not group:
                continue
                
            branch_x, branch_y = self._calculate_median_position(group)
            node_type = "buffer" if self.buffer_insertion else "branch"
            
            branch_node = ClockNode(
                id=self._next_node_id("BUF" if node_type == "buffer" else "BR"),
                x=branch_x, y=branch_y,
                node_type=node_type
            )
            
            if node_type == "buffer" and self.default_buffer:
                branch_node.buffer_ref = self._select_buffer_for_group(group)

            parent_node.add_child(branch_node)
            self._partition_recursive(branch_node, group, depth + 1)

    def _choose_axis(self, sinks: List[Sink], depth: int) -> str:
        if self.axis_mode == "x": return "x"
        if self.axis_mode == "y": return "y"
        if self.axis_mode == "alternate": return "x" if depth % 2 != 0 else "y"
            
        xs = [s.x for s in sinks]
        ys = [s.y for s in sinks]
        return "x" if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else "y"

    def _split_into_k_groups(self, sorted_sinks: List[Sink], k: int) -> List[List[Sink]]:
        """Разбивает массив на K сбалансированных групп"""
        if self.criterion == "balanced_count":
            n = len(sorted_sinks)
            return [sorted_sinks[i * n // k: (i + 1) * n // k] for i in range(k)]

        total_cap = sum(s.capacitance for s in sorted_sinks)
        target_step = total_cap / k
        
        groups = [[] for _ in range(k)]
        current_group = 0
        accumulated_cap = 0.0
        
        for s in sorted_sinks:
            groups[current_group].append(s)
            accumulated_cap += s.capacitance
            if accumulated_cap >= target_step * (current_group + 1) and current_group < k - 1:
                current_group += 1
                
        return groups

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
            
        total_cap = sum(s.capacitance for s in sinks)
        sorted_bufs = sorted(self.buffers.values(), key=lambda b: b.drive_strength)
        
        if total_cap < 15.0:
            return sorted_bufs[0]
        elif total_cap < 30.0 and len(sorted_bufs) > 1:
            return sorted_bufs[1]
        else:
            return sorted_bufs[-1]
