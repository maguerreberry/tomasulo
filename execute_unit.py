class _FunctionalUnits:
    class FunctionalUnit:
        current_instruction = None
        end_cycle = None

        def __init__(self, duration, name):
            self.duration = duration
            self.name = name
            self.queue = list()

        def __repr__(self):
            return str(self)

        def __str__(self):
            return ('{0.name}: {0.current_instruction} ends at {0.end_cycle} -- '
                    'duration {0.duration} queuelen {1}'.format(self, len(self.queue)))

        def busy(self, cycle):
            return self.end_cycle and cycle < self.end_cycle

        def _do_enqueue(self, current_cycle):
            if self.queue:
                self.queue.sort(key=lambda i: i.index)
                self.current_instruction = self.queue.pop(0)
                self.current_instruction.execute()
                self.end_cycle = current_cycle + self.duration

        def update(self, instruction_tracker, cdb, current_cycle):
            if current_cycle == self.end_cycle:
                self.current_instruction.enqueue_for_writeback()
                cdb.append(self.current_instruction)
            if not self.busy(current_cycle):
                self._do_enqueue(current_cycle)
            for instruction in self.queue:
                instruction.messages.add(('SD', self.name, self.current_instruction.index))

        def enqueue(self, instruction):
            self.queue.append(instruction)
            instruction.enqueue_for_execute()

    def __init__(self):
        int_fu = _FunctionalUnits.FunctionalUnit(1, 'Int FU')
        fp_add_fu = _FunctionalUnits.FunctionalUnit(5, 'FP Add FU')
        fp_mul_fu = _FunctionalUnits.FunctionalUnit(8, 'FP Mul FU')
        fp_div_fu = _FunctionalUnits.FunctionalUnit(15, 'FP Div FU')
        self.opcode_map = collections.defaultdict(lambda: int_fu)
        self.opcode_map.update({'ADD.D': fp_add_fu, 'MUL.D': fp_mul_fu,
                                'DIV.D': fp_div_fu})
        self.fu_list = [int_fu, fp_add_fu, fp_mul_fu, fp_div_fu]

    def enqueue(self, instruction):
        self.opcode_map[instruction.opcode].enqueue(instruction)

    def update(self, instruction_tracker, cdb, current_cycle):
        for fu in self.fu_list:
            fu.update(instruction_tracker, cdb, current_cycle)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return '\n'.join(str(fu) for fu in self.fu_list)

