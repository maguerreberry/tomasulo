Tomasulo.py
===========

This is a python module that implements Tomasulo's algorithm on a stream of
instructions and prints when each instruction entered the issue (IS), execute
(EX), write-back (WB), and commit (CM) stages.  It also notates where
instructions had to wait for data dependences or structural
dependences/hazards.

Input is a list of ``tomasulo.Instruction`` which are to be run.  Opcode is the
opcode of the instruction and is used to decide which functional unit to send
it to.  Write register is the name of the register that this instruction will
write to.  Read registers is an iterable of the register names that this
instruction reads.  You can see an example invocation in ``test.py``.

**Current Limitations**

- Hardware is not configurable.  Eventually it might be nice to be able to
  configure the functional units to have multiple units of a type or to change
  the mapping from opcode to functional unit.  Or to be able to
  commit/issue/write-back multiple instructions in a cycle.
- Limited input format.  It would be nice to be able to use as input a file
  with the instructions in text.
- Flexibility in running module.  Right now you have to build a python file and
  import this module.  It would be nice to be able to run tomasulo.py either
  directly from the command line or as a python module.
- Configurable write-back stage.  Currently all instructions use the WB stage.
  Store and branch instructions technically don't need to -- it might be nice to
  be able to make this simulator respect that.

If you have ideas, feel free to open an issue or submit patches or email me or
whatever.  I'd love to hear them. :-)
