#!/usr/bin/python
# -*- coding: utf-8 -*-

# Tomasulo Load-Store Queue 
class LSQobject:
    lsq = []
    lsq_size = 0

    def lsq_initialize(self, num_load_store_rs):
        self.lsq_size = num_load_store_rs
    
    #Indica si quedan entradaas libres en RS de load y store
    def lsq_available(self):
        if len(self.lsq) < self.lsq_size:
            return 1
        else:
            return -1
    
    #Agrego una entrada a la LSQ
    def lsq_add(self, ls_instr, ls_constant, ls_addr_val, ls_addr_reg, store_val, store_reg, rob_dest):
        #    1) LOAD  -> direccion (hasta EX) and valor (hasta MEM a menos que ocurra fwd) NO estan listos
        #    2) STORE -> direccion (hasta EX) no esta lista, el valor depende de los registros a los que haga referncia

        if len(self.lsq) < self.lsq_size:
            lsq_entry = { 
                "type" : ls_instr,    #(LD o SD)
                "dest" : rob_dest,   #Destino en la ROB
                "vj" : store_val,    #Valor a guardar en instruccion de SD
                "qj" : store_reg,    #Tag al valor a guardar en SD
                "vk" : ls_addr_val,    #registro de direccion
                "qk" : ls_addr_reg,    #Tag al registro de direccion
                "constant" : ls_constant,
                "address" : "-",
                "value" : "-", #valor traido de memoria en un LOAD
                "fwd" : "-"}    #Indica si se utiilizo FWD
            self.lsq.append(lsq_entry.copy())
        else:
            return -1
    
    def lsq_get_store_val(self, rob_entry):
        for entry in self.lsq:
            if entry["dest"] == rob_entry:
                return entry["vj"]
    
    def lsq_update_value(self, rob_entry, value):
        for index, entry in enumerate(self.lsq):
            if entry["qj"] == rob_entry:
                self.lsq[index]["vj"] = value
                self.lsq[index]["qj"] = "-"
            if entry["qk"] == rob_entry:
                self.lsq[index]["vk"] = value
                self.lsq[index]["qk"] = "-"
    
    def lsq_store_val_available(self, rob_entry):
        for entry in self.lsq:
            if entry["dest"] == rob_entry:
                if entry["vj"] != "-":
                    return 1
                else:
                    return -1
    
    def lsq_addr_reg_ready(self, rob_entry):
        for entry in self.lsq:
            if entry["dest"] == rob_entry:
                if entry["vk"] != "-":
                    #print "LSQ ADDRESS REG: " + str(entry["vk"])
                    return 1
                else:
                    return -1
        #print "FAILED to FIND LSQ ENTRY: " + rob_entry
        return -1
 
    def lsq_get_address_values(self, rob_entry):
        for entry in self.lsq:
            if entry["dest"] == rob_entry:
                return [entry["constant"], entry["vk"]]
                                
    def lsq_update_address(self, rob_entry, address):
        for index, entry in enumerate(self.lsq):
            if entry["dest"] == rob_entry:
                self.lsq[index]["address"] = address
                 
    def lsq_get_address(self, rob_entry):
        for entry in self.lsq:
            if entry["dest"] == rob_entry:
                return entry["address"]
                #print "FOUND LSQ UPDATE ADDRESS: " + str(entry["address"])
                
    def lsq_dequeue(self, rob_entry):
        #pop the oldest instruction from the queue
        if self.lsq[0]["dest"] == rob_entry:
            del self.lsq[0]
            return 1
        else:
            return -1

    def lsq_get_fwd_value(self, rob_entry):
        for entry in self.lsq:
            if entry["dest"] == rob_entry:
                return entry["value"]
            
    def lsq_fwd_flag_set(self, rob_entry):
        for entry in self.lsq:
            if entry["dest"] == rob_entry:
                if entry["fwd"] == 1:
                    return 1
                else:
                    return -1
    
    def lsq_forwarding(self, rob_entry):
        #print "FORWARDING FUNCTION: "
        # check if can forward a value to myself
        entry_index = 0
        for index, entry in enumerate(self.lsq):
            if entry["dest"] == rob_entry:
                entry_index = index
                addr = entry["address"]
                break
        #print "FORWARDING INDEX: " + str(entry_index)
        if entry_index != 0:
            for index in range(entry_index - 1, -1, -1):
                #print "LSQ INDEX: " + str(index)
                if self.lsq[index]["type"] == "SD" and self.lsq[index]["address"] == addr:
                    # forward if value is ready
                    #print "FORWARDING LSQ INDEX: " + str(index) + " - FOUNT STORE INSTR WITH THE SAME ADDR"
                    if self.lsq[index]["vj"] != "-":
                        self.lsq[entry_index]["value"] = self.lsq[index]["vj"]
                        #print "FORWARDING with " + str(self.lsq[index]["vj"])
                        self.lsq[entry_index]["fwd"] = 1
                        return 1
                        #print "FORWARDING FOUND"
                    break
        # if not return -1
        #print "FORWARDING NOT FOUND"
        return -1

    def lsq_print(self):
        print ("------------------------------------------------------------------------------------")
        print ("LOAD STORE QUEUE")
        print ("------------------------------------------------------------------------------------")    
        column_names = ["DEST", "TYPE", "VSD", "QSD", "VAddr", "QAddr", "CONST", "ADDR", "VAL", "FWD"]
        row_format ="{:^16}" * len(column_names)
        print (row_format.format(*column_names))
        for index, lsq_entry in enumerate(self.lsq):
            lsq_entry_list = [lsq_entry["dest"], lsq_entry["type"], lsq_entry["vj"], lsq_entry["qj"], lsq_entry["vk"], lsq_entry["qk"], lsq_entry["constant"], lsq_entry["address"], lsq_entry["value"], lsq_entry["fwd"]]
            print (row_format.format(*lsq_entry_list))
        print  