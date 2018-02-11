class InstructionTracker:
    """Holds onto the state of each instruction.

    Therefore also knows which instruction(s) are next to issue and when the
    instructions are all done executing.
    """

    class Instruction:
        """ Internal representation of an instruction.

        Tracks the state of the instruction and the pending state, and updates it
        for the new cycle.  Also tracks how many unsatisfied dependences this
        instruction currently has (when waiting in the reservation station) and
        which instruction in the stream this is.

        In addition, gives logging capabilities for the instruction to track things
        like RAW dependences and structural hazards/dependences.
        """
        _new_state = None
        state = 'unissued'
        states = set(('unissued', 'IS', 'reservation-station', 'queued-for-EX',
                      'EX', 'queued-for-WB', 'WB', 'waiting-for-commit', 'CM'))
        dependence_count = 0

        def __init__(self, instruction, index):
            self.opcode = instruction.opcode
            self.write_register = instruction.write_register
            self.read_registers = instruction.read_registers
            self.index = index
            self.history = list()
            self.messages = set()

        def _set_state(self, state):
            if state not in self.states:
                raise Exception("Tried to set illegal state {0}".format(state))
            self._new_state = state

        def update(self, new_cycle):
            if self._new_state:
                if self._new_state in set(('IS', 'EX', 'WB', 'CM')):
                    self.history.append((self._new_state, new_cycle))
                if self.state == 'EX':
                    self.history.append(('EX-end', new_cycle - 1))
                self.state = self._new_state
                self._new_state = None

        def issue(self):
            self._set_state('IS')

        def wait_in_reservation_station(self):
            self._set_state('reservation-station')

        def enqueue_for_execute(self):
            self._set_state('queued-for-EX')

        def execute(self):
            self._set_state('EX')

        def enqueue_for_writeback(self):
            self._set_state('queued-for-WB')

        def writeback(self):
            self._set_state('WB')

        def wait_for_commit(self):
            self._set_state('waiting-for-commit')

        def commit(self):
            self._set_state('CM')

        def ready_to_commit(self):
            return self.state in ('WB', 'waiting-for-commit')

        def __repr__(self):
            return str(self)

        def __str__(self):
            return ('{0.index}: {0.opcode} {0.write_register} {0.read_registers} state: '
                    '{0.state} pending state: {0._new_state} d_c: '
                    '{0.dependence_count}'.format(self))

        def final_dict(self):
            """Returns a dictionary summarizing when this instruction was in each
              stage and what dependences it had to wait on.
              """

            def format_msg(msg):
                return '{0} on {1} (from {2})'.format(*msg)

            def get_cycle(state):
                index = map(lambda x: x[0], self.history).index(state)
                if state == 'EX':
                    start_cycle = str(self.history[index][1])
                    end_cycle = get_cycle('EX-end')
                    if start_cycle != end_cycle:
                        return '{0!s}-{1}'.format(self.history[index][1], end_cycle)
                    else:
                        return start_cycle
                else:
                    return str(self.history[index][1])

            reg_iter = itertools.chain((self.write_register,), self.read_registers)
            instruction_text = '{0} {1}'.format(self.opcode, ', '.join(reg_iter))
            return {'index': self.index, 'instruction': instruction_text,
                    'IS': get_cycle('IS'), 'EX': get_cycle('EX'),
                    'WB': get_cycle('WB'), 'CM': get_cycle('CM'),
                    'messages': '; '.join(format_msg(m) for m in self.messages)}

    def __init__(self, instructions):
        self.instructions = [InstructionTracker.Instruction(instr, i) for
                             i, instr in enumerate(instructions)]

    def issue_next(self, reorder_buffer):
        unissued = filter(lambda i: i.state == "unissued", self.instructions)
        if unissued and not reorder_buffer.is_full():
            reorder_buffer.add(unissued[0])
            unissued[0].issue()

    def update(self, new_cycle):
        for instruction in self.instructions:
            instruction.update(new_cycle)
        if self.instructions[-1].state == 'CM':
            return True
        if new_cycle > 1000:
            print "failed to stop"
            return True

