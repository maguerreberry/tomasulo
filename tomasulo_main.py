#!/usr/bin/python
# -*- coding: utf-8 -*-

from sys import argv

import tomasulo_rat
import tomasulo_rs
import tomasulo_arf
import tomasulo_mem
import tomasulo_rob
import tomasulo_timing_table
import tomasulo_load_store_queue

# PARAMETROS GLOBALES
num_rob_entries = 128 
int_adder_properties = {
    "num_rs" : 2,
    "cycles_in_ex" : 1,
    "num_fus" : 1
}
fp_adder_properties = {
    "num_rs" : 3,
    "cycles_in_ex" : 4,
    "num_fus" : 1
}
fp_multiplier_properties = {
    "num_rs" : 2,
    "cycles_in_ex" : 8,
    "num_fus" : 1
}
load_store_unit_properties = {
    "num_rs" : 3,
    "cycles_in_ex" : 1,
    "cycles_in_mem" : 4,
    "num_fus" : 1
}

# ESTRUCTURAS GLOBALES  
instruction_buffer = []
memory = tomasulo_mem.MEMobject() 
arf = tomasulo_arf.ARFobject()
rat = tomasulo_rat.RATobject()
rs = tomasulo_rs.RSobject()
rob = tomasulo_rob.ROBobject()
timing_table = tomasulo_timing_table.TTobject() 
lsq = tomasulo_load_store_queue.LSQobject()

############################################################################################################
# MAIN
############################################################################################################		
def main(input_filename): # a
    #-------------------------------------------------
    # Initializacion de parametros y estructuras
    #-------------------------------------------------

    # Inicializacion de registros y memoria
    arf.reg_initialize()
    memory.mem_initialize()

    input_file_decoder(input_filename)
    
    # inicializar RAT
    rat.rat_initialize()
    # inicializar estaciones de reserva
    rs.rs_initialize(int_adder_properties["num_rs"], fp_adder_properties["num_rs"], fp_multiplier_properties["num_rs"])
    # initializar rob
    rob.rob_initialize(num_rob_entries)
    # initializar cola load store
    lsq.lsq_initialize(load_store_unit_properties["num_rs"])    
        
    available_int_fu = int_adder_properties["num_fus"] # cantidad de unidades funcionales disponibles
    available_ls_fu = load_store_unit_properties["num_fus"] # cantidad de unidades funcionales disponibles
    timing_table_entry_index = 0
    memory_is_in_use = 0 # contador de ciclos de memoria en uso
    memory_buffer = [] # [direccion, valor]
    cdb_in_use = 0 # disponibilidad del CDB
    arf_buffer = []
    cdb_buffer = [] # Valores para actualizar el CDB
    ls_buffer = [] # Guardo temporalmente direcciones de load y store
    stall_instruction_buffer = 0 # Sirve para detener la entrdad de instrucciones
    int_adder_fu_timer = [] # Contador de ciclos para reteraso en unidades funcionales
    load_inst_ready_to_dequeue = [] # para eliminar entradas en la LSQ
    #-------------------------------------------------
    # PIPELINE
    #-------------------------------------------------
    PC = 0 # Contador de programa, incrementado en 4
    cycle_counter = 0
    while(1):
		#ACTUALIZACION DE CLOCK
        cycle_counter = cycle_counter + 1
        available_fp_adder_fu = fp_adder_properties["num_fus"] 
        available_fp_mult_fu = fp_multiplier_properties["num_fus"] 
		
        # Actualiza el estado de la memoria, memory_buffer se llena en la ints de store
        if memory_is_in_use != 0:
            memory_is_in_use = memory_is_in_use - 1
            if memory_is_in_use == 0 and memory_buffer != []:
                memory.mem_write(memory_buffer[0], memory_buffer[1])
                lsq.lsq_dequeue(memory_buffer[2])
                memory_buffer = []
                        
        # Actualiza el estado de los registros, de enteros y flotantes.
        if arf_buffer != []:
            arf.reg_write(arf_buffer[0], arf_buffer[1])
            arf_buffer = []
        
        # Actualiza el common data bus.
        if cdb_buffer != []:
            cdb_update(cdb_buffer[0], cdb_buffer[1])
            cdb_buffer = []

        if cdb_in_use == 1:
            cdb_in_use = 0
        
        # CHECK LS BUFFER
        for index, entry in enumerate(ls_buffer):
            if cycle_counter >= (entry["ready_cycle"]):
                available_ls_fu = available_ls_fu + 1
                # update lsq
                lsq.lsq_update_address(entry["destination"], entry["address"])
                del ls_buffer[index]                
         
        # Chequeo el timer de la unidad de ejecucion de sumador de enteos 
        if cycle_counter in int_adder_fu_timer:
            available_int_fu = available_int_fu + 1 
        
        # LOAD DEQUEUE
        if len(load_inst_ready_to_dequeue) > 0:
            for index, entry in enumerate(load_inst_ready_to_dequeue):
                if lsq.lsq_dequeue(entry) == 1:
                    del load_inst_ready_to_dequeue[index]
        
        #############################
        #P DEBUG TABLAS EN CADA CICLO DE CLOCK
        #############################
        #rob.rob_print()
        #rs.rs_print()
        #lsq.lsq_print()
        #timing_table.time_table_print()
        #memory.mem_print_non_zero_values()
        #arf.reg_print()
        #rat.rat_print()
        
        # Imprimir resultados cuando se vacia la ROB y hemos leido todas la  instrucciones
        if (rob.rob_empty() == 1) and ((PC/4) >= len(instruction_buffer)) and (memory_is_in_use == 0):
            timing_table.time_table_print()
            arf.reg_print()
            memory.mem_print_non_zero_values()
            break
        
        #---------------------------------------------------------------------
        # ISSUE STAGE
        #---------------------------------------------------------------------
        rob_dest = "-" # Si se mantiene "-", significa que no se issue ninguna instruccion
        available_instuction_in_instruction_buffer = ((PC/4) < len(instruction_buffer))
        available_rob_entry = (rob.rob_available() == 1)

        #Chequeo que se den la condiciones para issue una nueva inst
        if stall_instruction_buffer == 0 and available_instuction_in_instruction_buffer and available_rob_entry:
            # obtengo y parseo instruccion del buffer
            instruction = instruction_buffer[int(PC/4)]
            instruction_parsed = instruction.split(" ")
            instruction_id = instruction_parsed[0]
            # verificar disponibilidad de ER segun el opcode  
            # Se configuran las estaciones de reserva segun el opcode de cada instaruccion     
            if instruction_id in ["ADD", "ADDI", "SUB"]:
                available_rs_entry = (rs.rs_available("int_adder_rs") != -1)
                if available_rs_entry:

                    # Chequear si tenemos los valores de qj y qk para ingresar a las estaciones de reserva
                    reg1 = get_current_reg_info(instruction_parsed[2]) # reg_name
                    if instruction_id in ["ADDI"]:
                        reg2 = [int(instruction_parsed[3]), "-"]
                    else:
                        reg2 = get_current_reg_info(instruction_parsed[3]) # reg_name
                    
                    rob_dest = rob.rob_instr_add(instruction, instruction_parsed[1],timing_table_entry_index)
                    
                    rat.int_rat_update(instruction_parsed[1], rob_dest) # update rat
                    
                    timing_table_entry_index = timing_table_entry_index + 1
                    
                    rs.rs_add("int_adder_rs", instruction_id, rob_dest, reg1[0], reg2[0], reg1[1], reg2[1]) # rs_name, i, op, dest, vj, vk, qj, qk
                    timing_table.timing_table_add(PC, instruction, cycle_counter)
                    PC = PC + 4
            elif instruction_id in ["ADD.D", "SUB.D"]: 
                available_rs_entry = (rs.rs_available("fp_adder_rs") != -1)
                if available_rs_entry:
                    reg1 = get_current_reg_info(instruction_parsed[2]) 
                    reg2 = get_current_reg_info(instruction_parsed[3])
                    rob_dest = rob.rob_instr_add(instruction, instruction_parsed[1], timing_table_entry_index)
                    rat.fp_rat_update(instruction_parsed[1], rob_dest) 
                    timing_table_entry_index = timing_table_entry_index + 1
                    rs.rs_add("fp_adder_rs", instruction_id, rob_dest, reg1[0], reg2[0], reg1[1], reg2[1]) # rs_name, i, op, dest, vj, vk, qj, qk
                    timing_table.timing_table_add(PC, instruction, cycle_counter)
                    PC = PC + 4
            elif instruction_id in ["MULT.D"]: 
                available_rs_entry = (rs.rs_available("fp_multiplier_rs") != -1)
                if available_rs_entry:
                
                    reg1 = get_current_reg_info(instruction_parsed[2]) 
                    reg2 = get_current_reg_info(instruction_parsed[3]) 
                    rob_dest = rob.rob_instr_add(instruction, instruction_parsed[1], timing_table_entry_index)
                    rat.fp_rat_update(instruction_parsed[1], rob_dest)
                    timing_table_entry_index = timing_table_entry_index + 1
                    rs.rs_add("fp_multiplier_rs", instruction_id, rob_dest, reg1[0], reg2[0], reg1[1], reg2[1]) # rs_name, i, op, dest, vj, vk, qj, qk
                    timing_table.timing_table_add(PC, instruction, cycle_counter)
                    PC = PC + 4
            elif instruction_id in ["SD"]:
                available_rs_entry = (lsq.lsq_available() != -1)
                if available_rs_entry:
                    
                    addr_reg = get_current_reg_info(instruction_parsed[2].split("(")[1].split(")")[0]) 
                    constant = instruction_parsed[2].split("(")[0]
                    
                    source_reg = get_current_reg_info(instruction_parsed[1]) # only needed for store instructions
                    rob_dest = rob.rob_instr_add(instruction, "-", timing_table_entry_index) # registro de destino nulo. 
                    timing_table_entry_index = timing_table_entry_index + 1
                    # no hace falta actualizatr la rat pq no se escribe ningun registro
                    #add entry to lsq
                    lsq.lsq_add(instruction_id, constant, addr_reg[0], addr_reg[1], source_reg[0], source_reg[1], rob_dest) # inst name, constante, v_addr, q_addr, v_fuente, q_fuente, rob destino (sirve para saber cuando haces el commit cuando haces el acceso a mem) 
                    timing_table.timing_table_add(PC, instruction, cycle_counter)
                    PC = PC + 4
            elif instruction_id in ["LD"]:
                available_rs_entry = (lsq.lsq_available() != -1)
                if available_rs_entry:
                    # add entry
                    #check if we have the needed values
                    addr_reg = get_current_reg_info(instruction_parsed[2].split("(")[1].split(")")[0]) # reg_name
                    constant = instruction_parsed[2].split("(")[0]
                    #specific to SD
                    source_reg = ["-", "-"] # pq no obtenes valor de un registro 
                    rob_dest = rob.rob_instr_add(instruction, instruction_parsed[1], timing_table_entry_index)
                    timing_table_entry_index = timing_table_entry_index + 1
                    #update rat
                    rat.rat_update(instruction_parsed[1], rob_dest) # need to update rat
                    #add entry to lsq
                    lsq.lsq_add(instruction_id, constant, addr_reg[0], addr_reg[1], source_reg[0], source_reg[1], rob_dest)
                    timing_table.timing_table_add(PC, instruction, cycle_counter)
                    PC = PC + 4
            else:
                print ("Invalid instruction!")
                exit(1)
 
        # El control del estado de las instrucciones se hace a traves de la ROB
        rob_entry = rob.rob_head_node(rob_dest) 
        while rob_entry != -1:
            
            rob_entry_state = rob.rob_get_state(rob_entry)
            rob_entry_instruction_id = rob.rob_get_instruction_id(rob_entry)
            if rob_entry_state == "MEM":
                #---------------------------------------------------------------------
                # MEM -> WB (Solo los LOAD entran a MEM) 
                #---------------------------------------------------------------------
                mem_stage_done = (timing_table.timing_table_check_if_done(rob.rob_get_tt_index(rob_entry), "MEM", cycle_counter) == 1)
                if mem_stage_done and cdb_in_use == 0:
                    # Se usa el CDB para enviar el valor recibido de memoria a todoas la estaciones
                    cdb_in_use = 1
                    # Chequeo si ocurrio un fwd en la LSQ debido a un store previo 
                    if lsq.lsq_fwd_flag_set(rob_entry) == 1:
                        result = lsq.lsq_get_fwd_value(rob_entry)
                    else:
                        #Busco el valor en memoria, porque no hubo un store previo
                        result = memory.mem_read(lsq.lsq_get_address(rob_entry))
                
                    #Una vez recibido el valor de load se debe eliminar la entrada en LSQ
                    load_inst_ready_to_dequeue.append(rob_entry)

                    cdb_buffer = [rob_entry, result]    
                    #Actualizo ROB
                    rob.rob_update_state(rob_entry, "WB")
                    timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "WB", cycle_counter, 1)
            elif rob_entry_state == "EX" and rob_entry_instruction_id == "LD":  
                #---------------------------------------------------------------------
                # EX -> MEM
                #---------------------------------------------------------------------
                ex_stage_done = (timing_table.timing_table_check_if_done(rob.rob_get_tt_index(rob_entry), "EX", cycle_counter) == 1)
                if ex_stage_done:
                    forwarding_happened = (lsq.lsq_forwarding(rob_entry) != -1)
                    if forwarding_happened:
                        #Actualizo el delay de MEM para que sea de un solo cilclo en fdw ya que no tiene que buscar en memoria
                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "MEM", cycle_counter, 1)
                        #update rob
                        rob.rob_update_state(rob_entry, "MEM")
                    elif memory_is_in_use == 0:
                        #cantidad de ciclos que va a estar en uso la memoria
                        memory_is_in_use = load_store_unit_properties["cycles_in_mem"]

                        #Seteo timer con los ciclos necesarios en memoria
                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "MEM", cycle_counter, load_store_unit_properties["cycles_in_mem"])
                        #update rob
                        rob.rob_update_state(rob_entry, "MEM")                        
            elif rob_entry_state == "EX": # not ld instruction   
                #---------------------------------------------------------------------
                # EX -> WB STAGE
                #--------------------------------------------------------------------- 
                ex_stage_done = (timing_table.timing_table_check_if_done(rob.rob_get_tt_index(rob_entry), "EX", cycle_counter) == 1)

                if ex_stage_done and cdb_in_use == 0:
                    # cambio al estado WB               
                    if rob_entry_instruction_id in ["ADD", "ADDI", "SUB", "ADD.D", "SUB.D", "MULT.D"]:
                        cdb_in_use = 1
                        if rob_entry_instruction_id in ["ADD", "ADDI"]:
                            # hago la suma
                            values = rs.rs_get_values("int_adder_rs", rob_entry)
                            result = values[0] + values[1]
                            # escribo el resulatdo en CDB                      
                            cdb_buffer = [rob_entry, result]
                        elif rob_entry_instruction_id in ["SUB"]:
                            # perform subtraction
                            values = rs.rs_get_values("int_adder_rs", rob_entry)
                            result = values[0] - values[1]
                            # add result to cdb buffer
                            cdb_buffer = [rob_entry, result]
                        elif rob_entry_instruction_id == "ADD.D":
                            # perform addition
                            values = rs.rs_get_values("fp_adder_rs", rob_entry)
                            result = float(values[0] + values[1])
                            # add result to cdb buffer
                            cdb_buffer = [rob_entry, result]
                        elif rob_entry_instruction_id == "SUB.D":
                            # perform addition
                            values = rs.rs_get_values("fp_adder_rs", rob_entry)
                            result = float(values[0] - values[1])
                            # add result to cdb buffer
                            cdb_buffer = [rob_entry, result]
                        elif rob_entry_instruction_id == "MULT.D":
                            # perform multiplication
                            values = rs.rs_get_values("fp_multiplier_rs", rob_entry)
                            result = float(values[0]*values[1])
                            # add result to cdb buffer
                            cdb_buffer = [rob_entry, result]
                        # Vacio la ER
                        rs.rs_clear_entry(rob_entry)
                        rob.rob_update_state(rob_entry, "WB")

                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "WB", cycle_counter, 1)
                    elif rob_entry_instruction_id in ["SD"]:
                        #Cuando el valor esta listo para escribir se advierte a la ROB, y desde la ROB se escribe la memoria
                        if lsq.lsq_store_val_available(rob_entry) != -1:
                            #Escribo CDB para que el valor este disponible para todas las estaciones
                            cdb_in_use = 1
                            
                            cdb_buffer = [rob_entry, lsq.lsq_get_store_val(rob_entry)]                                               
                            #Actualizo ROB
                            rob.rob_update_state(rob_entry, "WB")
                            timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "WB", cycle_counter, 1)                
            elif rob_entry_state == "ISSUE":    
                #---------------------------------------------------------------------
                # ISSUE -> EX
                #---------------------------------------------------------------------            
                if rob_entry_instruction_id in ["ADD", "ADDI"]:
                    # me fijo en las estaciones de reserva si esta lista la instaruccion para ejecutar
                    no_dependencies = (rs.rs_no_dependencies("int_adder_rs", rob_entry) != -1)
                    if no_dependencies and available_int_fu != 0:
                        # utlizo una unidad funcional
                        available_int_fu = available_int_fu - 1
                        #update stage info in rob
                        rob.rob_update_state(rob_entry, "EX")
                        #update stage infor in tt
                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "EX", cycle_counter, int_adder_properties["cycles_in_ex"])
                        #stero el contador de ciclos de EX
                        int_adder_fu_timer.append(cycle_counter + int_adder_properties["cycles_in_ex"])
                elif rob_entry_instruction_id in ["SUB"]:
                    no_dependencies = (rs.rs_no_dependencies("int_adder_rs", rob_entry) != -1)
                    if no_dependencies and available_int_fu != 0:
                        available_int_fu = available_int_fu - 1
                        #update stage info in rob
                        rob.rob_update_state(rob_entry, "EX")
                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "EX", cycle_counter, int_adder_properties["cycles_in_ex"])
                        int_adder_fu_timer.append(cycle_counter + int_adder_properties["cycles_in_ex"])
                elif rob_entry_instruction_id == "ADD.D":
					
                    no_dependencies = (rs.rs_no_dependencies("fp_adder_rs", rob_entry) != -1)
                    if no_dependencies and available_fp_adder_fu != 0:
                        available_fp_adder_fu = available_fp_adder_fu - 1
                        rob.rob_update_state(rob_entry, "EX")
                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "EX", cycle_counter, fp_adder_properties["cycles_in_ex"])
                elif rob_entry_instruction_id == "SUB.D":
					
                    no_dependencies = (rs.rs_no_dependencies("fp_adder_rs", rob_entry) != -1)
                    if no_dependencies and available_fp_adder_fu != 0:
                        available_fp_adder_fu = available_fp_adder_fu - 1
                        rob.rob_update_state(rob_entry, "EX")
                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "EX", cycle_counter, fp_adder_properties["cycles_in_ex"])
                elif rob_entry_instruction_id == "MULT.D":
                    no_dependencies = (rs.rs_no_dependencies("fp_multiplier_rs", rob_entry) != -1)
                    if no_dependencies and available_fp_mult_fu != 0:
                        available_fp_mult_fu = available_fp_mult_fu - 1
                        rob.rob_update_state(rob_entry, "EX")
                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "EX", cycle_counter, fp_multiplier_properties["cycles_in_ex"])
                elif rob_entry_instruction_id in ["SD", "LD"]: # Calculo direcciones
                    no_dependencies = (lsq.lsq_addr_reg_ready(rob_entry) != -1)
                    if no_dependencies and available_ls_fu != 0:
                        #Utlizo la unidad funcional para calcular la direccion
                        available_ls_fu = available_ls_fu - 1
						# calcualo la direccion
                        values = lsq.lsq_get_address_values(rob_entry)
                        ls_address = int(values[0])*4 + int(values[1])
                        # Actualizacion de direcciones de load y store a traves de la_buffer
                        ls_buffer.append({"destination" : rob_entry, "address" : ls_address, "ready_cycle" : cycle_counter + load_store_unit_properties["cycles_in_ex"]}.copy())
                        # actualizo la entrada en ROB
                        rob.rob_update_sd_destination(rob_entry, ls_address)
                        
                        rob.rob_update_state(rob_entry, "EX")
                        timing_table.timing_table_update(rob.rob_get_tt_index(rob_entry), "EX", cycle_counter, load_store_unit_properties["cycles_in_ex"])
                        
            rob_entry = rob.rob_next(rob_entry, rob_dest) # obtengo la proxima entrada en a rob para analizar
        
        #---------------------------------------------------------------------
        # WB -> COMMIT STAGE
        #---------------------------------------------------------------------
        rob_entry_data = rob.rob_check_if_ready_to_commit() 
        #rob_entry_data = [tt_index, destination, value, instruction_id, rob_entry_name]

        if rob_entry_data != -1:
            if rob_entry_data[3] in ["ADD", "ADDI", "SUB", "ADD.D", "SUB.D", "MULT.D", "LD"]: 
                #CMuevo el puntero de commit 
                rob.rob_commit() # [tt_index, destination, value, instruction_id, rob_entry_name]
                cycles_in_commit = 1
                #Escribo registros en el buffer ARF
                arf_buffer = [rob_entry_data[1], rob_entry_data[2]] # [reg_dest, valor]

                #Si hay una entrada en la RAT que apunta hacia este ROB, la borro
                if rat.rat_get(rob_entry_data[1]) == rob_entry_data[4]:
                    rat.rat_update(rob_entry_data[1], rob_entry_data[1])
                timing_table.timing_table_update(rob_entry_data[0], "COMMIT", cycle_counter, cycles_in_commit)    
            elif rob_entry_data[3] == "SD" and memory_is_in_use == 0:
                rob.rob_commit() 
                cycles_in_commit = 1
                #Escribo el buffer de memoria
                memory_buffer = [rob_entry_data[1], rob_entry_data[2], rob_entry_data[4]] 
                #Ocupo la memoria
                cycles_in_commit = load_store_unit_properties["cycles_in_mem"]
                memory_is_in_use = load_store_unit_properties["cycles_in_mem"]                
                timing_table.timing_table_update(rob_entry_data[0], "COMMIT", cycle_counter, cycles_in_commit)

############################################################################################################
# DECODIFICADOR DE ARCHIVO DE ENTRADA
############################################################################################################		
def input_file_decoder(input_filename):
    global instruction_buffer
    input_file = open(input_filename, 'r')
    for line_not_split in input_file:
        line_not_split = line_not_split.upper().split("\n")[0]
        line = line_not_split.upper().split(" ")

        if(line[0] == "REG"):
            # Inicializacion de registros
            arf.reg_write(line[1], line[2])
        elif(line[0] == "MEM"):
            # Inicializacion de memoria
            memory.mem_write(line[1], line[2])
        elif(line_not_split != "" and line[0] != "#"): # if it isn't 
            # Lectura de instrucciones
            instruction_buffer.append(line_not_split)
############################################################################################################

############################################################################################################
def get_current_reg_info(reg_name): # returns [v, q]

    #A traves de la RAT se obtiene el estado (disponibilidad) del valor de un registro
    if reg_name.startswith("R"):
        reg_value = rat.int_rat_get(reg_name)
    else:
        reg_value = rat.fp_rat_get(reg_name)
        
    if reg_value.startswith("ROB"):
        rob_entry_value = rob.rob_get_value(reg_value)
        if str(rob_entry_value) == "-":
            return ["-", reg_value]
        else: 
            return [rob_entry_value, "-"]    
    else: 
        return [arf.reg_read(reg_value), "-"]
        
def cdb_update(destination, value):
    #Se actualizan las tablass que dependen del valores publicados en el CDB
    
    # Estaciones de reserva
    rs.rs_update_value(destination, value)
  
    # Cola de Load y Store
    lsq.lsq_update_value(destination, value)
    
    # Buffer de Reordenamiento
    rob.rob_update_value(destination, value)
############################################################################################################

if __name__ == "__main__":
    if len(argv) > 1:
        main(argv[1]) 
    else:
        print ("Por favor ingrese un archivo de entrada")
        exit(1)