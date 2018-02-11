class _ReorderBuffer:
    """Mimics a reorder buffer.

      Holds instructions that are add()ed to it, lets you know if it is full, and
      can do a commit.
    """
    def __init__(self, length=1e6):
        self.storage = list()
        self.length = length  # Default arg is basically infinity

    def add(self, instruction):
        if self.is_full():
            raise Exception("Reorder buffer just got too full!! Oops!")
        self.storage.append(instruction)

    def is_full(self):
        return len(self.storage) >= self.length

    def commit(self):
        if len(self.storage) == 0:
            return
        head = self.storage[0]
        if head.ready_to_commit():
            head.commit()
            self.storage.pop(0)

    def IS_instruction_iterator(self, instruction_tracker):
        return itertools.ifilter(lambda i: i.state == "IS", self.storage)
