#!/usr/bin/env python

import collections
import instruction as instr
import ROB
import execute_unit

Instruction = collections.namedtuple('Instruction', ('opcode',
                                                     'write_register', 'read_registers'))
"""This is the instruction tuple.  The first value is the opcode of the instruction, the second the register it will write to (or None), and the third is an iterable of the registers that the instruction will read from.

So the instruction:
    ADD.D F2, F0, F4
Would become:
    Instruction(opcode='ADD.D', write_register='F2', read_registers=('F0', 'F4'))
"""

def run(input_instructions):
    """This is the primary computation point of this module.

      It takes a list of Instructions, and generates the output structure.

      Each instruction should be a tomasulo.Instruction.
    """
    cycle = 0
    instruction_tracker = instr.InstructionTracker(input_instructions)
    reorder_buffer = ROB._ReorderBuffer()
    functional_units = execute_unit._FunctionalUnits()

    # The register file is a mapping from register to either None or the index of
    # the instruction that is currently in the process of producing the new value
    # for that register.  It's set in the IS stage and removed in the WB stage.
    register_file = collections.defaultdict(lambda: None)

    # The reservation station is a mapping from the index of an instruction
    # currently in progress to a list of indices of instructions that are waiting
    # for this value.  Instructions add themselves to this list in the IS stage if
    # they are waiting for the key instruction to finish.  In the WB stage, we
    # remove entries and pass them along to the functional units if they're ready
    # to go.
    reservation_station = collections.defaultdict(list)

    # The cdb is a list of instructions queued up to enter writeback.  At the WB
    # stage, the instruction with the lowest index is put on the cdb, and the
    # others wait until a later cycle.
    cdb = list()

    while not instruction_tracker.update(cycle):
        # Set up next instruction to issue next time
        instruction_tracker.issue_next(reorder_buffer)

        # Deal with instructions currently in issue stage
        for instruction in reorder_buffer.IS_instruction_iterator(instruction_tracker):
            has_dependence = False
            for register in instruction.read_registers:
                if register_file[register] is not None:
                    has_dependence = True
                    instruction.wait_in_reservation_station()
                    instruction.dependence_count += 1
                    reservation_station[register_file[register]].append(instruction.index)
                    instruction.messages.add(('RAW', register, register_file[register]))
            if not has_dependence:
                functional_units.enqueue(instruction)
            register_file[instruction.write_register] = instruction.index

        # Deal with EX stage
        functional_units.update(instruction_tracker, cdb, cycle)

        # Deal with WB stage
        if cdb:
            cdb.sort(key=lambda x: x.index)
            for instruction in cdb[1:]:
                instruction.messages.add(('SD', 'CDB', cdb[0].index))
            instruction = cdb.pop(0)
            instruction.writeback()
            waiting_instructions = [instruction_tracker.instructions[i] for i in
                                    reservation_station[instruction.index]]
            for instr in waiting_instructions:
                instr.dependence_count -= 1
                if instr.dependence_count == 0:
                    functional_units.enqueue(instr)
            del reservation_station[instruction.index]
            if register_file[instruction.write_register] == instruction.index:
                del register_file[instruction.write_register]

        # Deal with CM stage
        reorder_buffer.commit()

        cycle += 1

    # This is debug stuff to dump the state of various hardware pieces.  I'm
    # leaving it here should you need it to debug stuff.
    #
    #  for instruction in reorder_buffer.storage:
    #    print instruction
    #  print("reservation_station_state",
    #    ['{0!s}: {1}'.format(k, ', '.join(map(lambda x: str(x), v))) for k, v in
    #    reservation_station.iteritems() if v])
    #  print("reg_file_state:", ['{0}: {1!s}'.format(k, v) for k, v in register_file.iteritems() if v is not None])
    #  print functional_units

    # Print final state:
    format_str = '{index: >2} {instruction: >19}{IS: >5}{EX: >9}{WB: >5}{CM: >5}  {messages}'
    print format_str.format(index='', instruction='Instruction', IS='IS',
                            EX='EX', WB='WB', CM='CM', messages='Messages')
    print 80 * '-'
    for instruction in instruction_tracker.instructions:
        print format_str.format(**instruction.final_dict())
