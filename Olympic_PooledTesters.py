#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  4 20:21:39 2022

@author: CameronField
"""

import simpy
import random
import pandas as pd
import matplotlib.pyplot as plt

random.seed(60)


class g:
    """Global class to establish scenario parameters"""
    
   ##Customer Demand
    d_arr = 10                #Average customer demand in orders per day (orders/day)
    d_std = 5                 #Standard deviation of customer demand (orders/day)
    d_intarrival = 24/d_arr   #Translates demand in orders per day to hours between orders
    d_int_std = 24/d_std      #Translates standard deviation of demand to std_dev of demand interarrival times
    
   ##Order Processing Parameters
    units_per_order= 50       #How many units are purchased in every order
    lots_per_order = 5        #How many lots is the order broken into
    units_per_lot = units_per_order/lots_per_order    #Converts units per order to units per lot
      
   ##Contract Financial Parameters
    cogs = 75                  #Average cost per unit (sum of cost of raw goods of one unit) ($)
    wholesale_price = 180      #The contractually agreed upon wholesale unit price that the customer is paying for finished units ($)
    quoted_lead = 60           #Contractually agreed upon lead time for one order (hrs)
    order_revenue = wholesale_price * units_per_order      #Revenue for one order ($)
    hourly_penalty = 600       #How much revenue you will forfeit for every hour late (in $)
 
   ##Factory Management Parameters
    tester_hr_wage = 17        #Hourly wage of one tester 
    testers = 15+15+30
    
   ##Stages 1-4 Parameters 
    #Stage 1
    lot_time1 = 0.5            #How many hours it takes to set up one lot to go through an etching machine   
    mean_etching = 0.15        #How many hours on average it takes for the etching machine to etch one unit
    std_etching = 0.02         #Standard deviation of etching time per unit (in hrs/unit)
    machines1 = 20             #Number of etching machines the plant can use
    
    #Stage 1 Testing
    mean_test1 = 0.4           #How many hours on average it takes for one tester to ensure the unit etchings are within specification
    std_test1 = 0.15            #Standard deviation of test duration (hrs/unit)
    p_fail_test1 = 0.05        #Probability of a unit failing the etch testing
    testers1 = 15              #Number of etch testers 
    
    #Stage 2 Assembly 
    mean_assembly = 0.5        #How many hours on average it takes for one machine to do assembly stage (hrs/unit)
    std_assembly = 0.15        #Standard deviation of asembly stage time per unit (hrs/unit)
    machines2 = 10             #Number of assembly machines 
    
    #Stage 2 Testing
    mean_test2 = 0.5           #How many hours on average it takes one tester to conduct a functions check on one unit (hrs/unit)
    std_test2 = 0.1            #Standard deviation of average assembly test
    p_fail_test2 = 0.015       #Probaiblity of a unit failing the assembly test
    testers2 = 15              #Number of assembly testers
    
    #Stage 3 Finishing
    lot__time3 = 0.5           #How many hours on it takes to set up one lot on the finishing machines (hrs/lot)
    mean_finishing = 0.2       #How many hours on average it takes for one machine to conduct finishing on one unit (hrs/unit)
    std_finishing = 0.15       #Standard deviation of average finishing time (hrs/unit)
    machines3 = 7              #Number of finishing machines
    
    #Stage 3 Testing
    mean_test3 = 0.15          #How many hours on average it takes one tester to conduct final testing on a unit (hrs/unit)
    std_test3 = 0.1            #Standard deviation of average final testing (hrs/unit)
    p_fail_test3 = 0.015       #Probability of a unit failing the final functions testing
    testers3 = 30              #Number of final functions check testers
    
    #Stage 4 Packaging and Shipping
    mean_ship = 7              #How many hours on average it takes to package and ship a single order to the customer (hrs/order)
    std_ship = .5              #Standard deviation of average time for packaging and shipping of a single order (hrs/order)
    
    order_service_level = 0.95 #Metric used later to show order fill time at a specific service level 
    
    sim_duration = 60*24       #Simulation duration (hrs)
    
class Lot: 
    """Class that tracks the id attributes and time performance of every lot"""
    
    def __init__(self, unique_id, order_id, lot_id):
        self.unique_id = unique_id
        self.order_id = order_id
        self.id = lot_id
        self.start_time = 0
        self.end_time = 0
        
        
class Olympic_Model:
    """This class is the model itself, it will run until the simulation duration is complete. 
       No global variables are re-defined or changed when model is executed"""
       
    def __init__(self, run_number):
        self.env = simpy.Environment()
        self.run_number = run_number
        self.unique_id_counter = 1
        self.order_counter = 0
        self.lot_counter = 1
        self.cost_per_lot = g.units_per_lot*g.cogs
        self.failed_tests = 0

        
        self.etch_machine = simpy.Resource(self.env, capacity = g.machines1)
        self.assembly_machine = simpy.Resource(self.env, capacity = g.machines2)
        self.finishing_machine = simpy.Resource(self.env, capacity = g.machines3)
        
        #self.etch_tester = simpy.Resource(self.env, capacity = g.testers1)
        #self.assembly_tester = simpy.Resource(self.env, capacity = g.testers2)
        #self.finishing_tester = simpy.Resource(self.env, capacity = g.testers3)
        self.testers = g.testers -4
        self.tester = simpy.Resource(self.env, capacity = self.testers)
        self.hrly_test_expense = self.testers * g.tester_hr_wage
        
        #Create dataframe to store the information about every lot
        self.lots_df = pd.DataFrame()
        #Datafrme to store information about every completed order
        self.orders_df = pd.DataFrame()
        #Dataframe to store time series data about queue lengths
        self.q_df = pd.DataFrame()
        #Dataframe to store time series data of cash position
        self.cash_df = pd.DataFrame()
        
    def log_cash(self, time, revenue, cogs, wages, note):
        """Function that, when called, logs the change in cash position to the firm's books.
           For this model, only revenue generated from completed orders, 
           cost of goods sold, and wage expenses are logged as cash expenses."""
           
        cash_df_to_add = pd.DataFrame({"Time":[time],
                                           "Revenue":[revenue],
                                           "COGS_Expense":[cogs],
                                           "Wage_Expense":[wages],
                                           "Note":[note]})
        #cash_df_to_add.set_index("Time", inplace=True)
        self.cash_df = self.cash_df.append(cash_df_to_add)
            
    def profit_cumsum(self, data):
        """Function that adds columns to the cash dataframe that accumulates the change in cash position over time. 
           This will be used later to plot our P/L."""
           
        data["Cumulative_Revenue"] = data["Revenue"].cumsum()
        data["Cumulative_COGS"] = data["COGS_Expense"].cumsum()
        data["Cumulative_Wage_Expense"]=data["Wage_Expense"].cumsum()
        data["Cumulative_Profits"] = data.apply(lambda row: row["Cumulative_Revenue"] - row["Cumulative_COGS"] - row["Cumulative_Wage_Expense"], axis=1)
            
    def log_queue(self, etch, assembly, finishing, testers):
         """Function that will log to a dataframe the status of every machine at a specific point in time. 
           Datapoints include queue length and utilization rates."""
           
         while True:  
             q_df_to_add = pd.DataFrame({"Time":[self.env.now],
                                         "Total_Orders":[self.order_counter],
                                         "Etch_Q_Length":[len(etch.queue)],
                                         "Assembly_Q_Length": [len(assembly.queue)],
                                         "Finishing_Q_Length":[len(finishing.queue)],
                                         "Etch_Utilization":[100*etch.count/g.machines1],
                                         "Assembly_Utilization":[100*assembly.count/g.machines2],
                                         "Finishing_Utilization":[100*finishing.count/g.machines3],
                                         "Testers_Utilization":[100*testers.count/g.testers],
                                         "Failed_Tests":[self.failed_tests]})
             self.q_df = self.q_df.append(q_df_to_add)  
             yield self.env.timeout(g.sim_duration/100)
             
    def log_wage_expense(self):
        """Function that logs the total wage expense of all the testers every hour."""
        
        while True:
            self.log_cash(self.env.now,0,0,self.hrly_test_expense, "Wage_Expense")
            yield self.env.timeout(1)
            
    def store_lot_results(self,lot):
        """Function that stores the attribute data for every lot once it completes the production process"""
        
        df_to_add = pd.DataFrame({"Unique_ID":[lot.unique_id],
                                  "Order_ID":[lot.order_id],
                                  "Lot_ID":[lot.id], 
                                  "Start_Time":[lot.start_time],
                                  "End_Time":[lot.end_time]})
        df_to_add["Lot_Process_Time"] = df_to_add.apply(lambda row: row["End_Time"] - row["Start_Time"], axis=1)
        df_to_add.set_index("Unique_ID", inplace=True)
        self.lots_df = self.lots_df.append(df_to_add)
        
    def store_order_results(self, lot, lot_data):
        """Function that stores the attribute data of every completed order.
           This function is called only when all lots of an order have completed 
           the production process and the order was packaged and delivered to the customer"""
           
        df_to_add = pd.DataFrame({"Order_ID":[lot.order_id], 
                                  "Start_Time":[lot_data[lot_data.Order_ID == lot.order_id]["Start_Time"].min()],
                                  "End_Time":[lot_data[lot_data.Order_ID == lot.order_id]["End_Time"].max()]})
        df_to_add["Order_Process_Time"] = df_to_add.apply(lambda row: row["End_Time"] - row["Start_Time"] + random.gauss(g.mean_ship, g.std_ship), axis=1)
        df_to_add["Revenue_Generated"] = df_to_add.apply(lambda row: g.order_revenue if row["Order_Process_Time"] <= g.quoted_lead else max(0,g.order_revenue - ((row["Order_Process_Time"]-g.quoted_lead)*g.hourly_penalty)), axis=1)
        self.orders_df = self.orders_df.append(df_to_add)
    
    def etch_and_test(self,lot):
        """This is the function that models the etching and etch testing stages.
           If a lot fails a test, it will continue to call this function until it passes the etch test.
           This function is called recursively when a test failure occurs."""
           
        with self.etch_machine.request() as req:
            yield req 
            sampled_etch_duration = max(0,random.gauss(g.mean_etching, g.std_etching))
            yield self.env.timeout((sampled_etch_duration*g.units_per_lot)+g.lot_time1)
        with self.tester.request() as req:
            yield req
            sampled_test1_duration = max(0,random.gauss(g.mean_test1, g.std_test1))
            yield self.env.timeout(sampled_test1_duration*g.units_per_lot)
            fail_test = random.uniform(0,1)
            if fail_test < g.p_fail_test1:
                self.failed_tests +=1
                yield self.env.process(self.etch_and_test(lot))
            else: pass 
        
    def assembly_and_test(self,lot):
        """This is the function that models the assembly and assembly testing stages.
           If a lot fails a test, it will continue to call this function until it passes the assembly test.
           This function is called recursively when a test failure occurs."""
           
        with self.etch_machine.request() as req:
            yield req 
            sampled_assembly_duration = max(0,random.gauss(g.mean_assembly, g.std_assembly))
            yield self.env.timeout(sampled_assembly_duration*g.units_per_lot)
            
        with self.tester.request() as req:
            yield req
            sampled_test2_duration = max(0,random.gauss(g.mean_test2, g.std_test2))
            yield self.env.timeout(sampled_test2_duration*g.units_per_lot)
            fail_test = random.uniform(0,1)
            
            if fail_test < g.p_fail_test2:
                self.failed_tests +=1
                yield self.env.process(self.assembly_and_test(lot))
            else: pass 
        
    def finishing_and_test(self,lot):
        """This is the function that models the finishing and final testing stages.
           If a lot fails a test, it will continue to call this function until it passes the final test.
           This function is called recursively when a test failure occurs."""
           
        with self.finishing_machine.request() as req:
            yield req 
            sampled_finishing_duration = max(0,random.gauss(g.mean_finishing, g.std_finishing))
            yield self.env.timeout(sampled_finishing_duration*g.units_per_lot)
            
        with self.tester.request() as req:
            yield req
            sampled_test3_duration = max(0,random.gauss(g.mean_test3, g.std_test3))
            yield self.env.timeout(sampled_test3_duration*g.units_per_lot*g.units_per_lot)
            fail_test = random.uniform(0,1)
            
            if fail_test < g.p_fail_test3:
                self.failed_tests +=1
                yield self.env.process(self.finishing_and_test(lot))
            else: pass 
   
    def generate_orders(self):
        """First generator function in the simpy environment. This function simulates order demand arriving to the factory.
           Demand is modeled as following a normal distribution, demand is inputted into the system as an interarrival time.
           Orders are then split into lots and lots are send through the production process."""
           
        while True:
            self.order_counter += 1
            self.lot_counter = 1
            #print(f"Order {self.order_counter} has been requested at {self.env.now:.5f}")
            for x in range(g.lots_per_order):
                l = Lot(self.unique_id_counter,self.order_counter, self.lot_counter)
                self.unique_id_counter += 1
                self.lot_counter += 1
                self.log_cash(self.env.now, 0, self.cost_per_lot,0,"COGS")
                self.env.process(self.lot_flow(l))
                #print(f"Lot {self.lot_counter} of order {self.order_counter} has been created")
            sampled_interarrival = max(0,random.gauss(g.d_intarrival, g.d_int_std))
            yield self.env.timeout(sampled_interarrival)
                
    def lot_flow(self,lot):
        """This function instantiates the flow of a single lot as it flows through the production process.
           Lot attributes, like start time and end time, are logged through this process. 
           Once a lot is completed in the system, a function within the lot_flow function checks whether or not all lots of the order are completed.
           If all lots of the order have completed the process flow, then the order is logged as being complete and revenue is recorded in the cash dataframe."""
        
        lot.start_time = self.env.now
        yield self.env.process(self.etch_and_test(lot))
        yield self.env.process(self.assembly_and_test(lot))
        yield self.env.process(self.finishing_and_test(lot))
        lot.end_time = self.env.now
        self.store_lot_results(lot)
        #print(f"Lot {lot.id} of order {lot.order_id} finished at {self.env.now}")
        if len(self.lots_df[self.lots_df.Order_ID == lot.order_id]) == g.lots_per_order:
            #print(f"*****Order {lot.order_id} finished at {self.env.now}")
            self.store_order_results(lot, self.lots_df)
            #print(self.orders_df)
            revenue = self.orders_df[self.orders_df.Order_ID == lot.order_id]["Revenue_Generated"][0]
            self.log_cash(self.env.now,revenue, 0,0,"Order Revenue")
            
    def run(self):
        """Function that when called, instantiates the model for a single run.
           When the model is complete, all dataframes are transferred from pandas df to .csv format"""
        self.env.process(self.generate_orders())
        self.env.process(self.log_queue(self.etch_machine, self.assembly_machine, self.finishing_machine, self.tester))
        self.env.process(self.log_wage_expense())
        self.env.run(until = g.sim_duration)
        self.profit_cumsum(self.cash_df)
        self.cash_df.to_csv('cash_data.csv')
        self.q_df.to_csv('queue_data.csv')
        self.lots_df.to_csv('lot_data.csv')
        self.orders_df.to_csv('orders_data.csv')
        
olympic_model = Olympic_Model(1)
olympic_model.run()


q_plot = pd.read_csv("queue_data.csv")
profit_plot = pd.read_csv("cash_data.csv")
order_plot = pd.read_csv("orders_data.csv")

fig, ax = plt.subplots()
ax.plot(q_plot.Time, q_plot.Etch_Q_Length, label = "Etching Stage", color = 'g', linestyle = 'dashed')
ax.plot(q_plot.Time, q_plot.Assembly_Q_Length, label = "Assembly Stage", color = 'b', linestyle = 'dashed')
ax.plot(q_plot.Time, q_plot.Finishing_Q_Length, label = "Finishing Stage,", color = 'r',linestyle = 'dashed')
plt.xlabel('Simulation Time (hrs)')
plt.ylabel('Queue Length (lots)')
plt.title(f'Queue Length by Stage when Demand = {g.d_arr} orders/day')
plt.legend()
plt.grid()
plt.show()   

fig, ax = plt.subplots()
#ax.plot(q_plot.Time, q_plot.Etch_Utilization, label = "Etching Stage", color = 'g', linestyle = 'dashed', linewidth = 1)
#ax.plot(q_plot.Time, q_plot.Assembly_Utilization, label = "Assembly Stage", color = 'b', linestyle = 'dashed', linewidth = 1)
#ax.plot(q_plot.Time, q_plot.Finishing_Utilization, label = "Finishing Stage,", color = 'r',linestyle = 'dashed', linewidth = 1)
ax.plot(q_plot.Time, q_plot.Testers_Utilization, label = "Finishing Testing,", color = 'r', linewidth = 1)
plt.xlabel('Simulation Time (hrs)')
plt.ylabel('Utilization (%)')
plt.title('Testers Utilization vs. Time')
#plt.legend()
plt.grid()
plt.show()  
    
fig, cx = plt.subplots()
cx.scatter(order_plot.End_Time, order_plot.Order_Process_Time, color = 'k', s=5)
plt.tight_layout()
plt.xlabel('Simulation Time (hrs)')
plt.ylabel('Order Process Time (hrs)')
plt.title('Filled Order Lead Times vs Simulation Time')
plt.grid()
plt.show()

fig, dx = plt.subplots()
dx.plot(profit_plot.Time, profit_plot.Cumulative_Revenue, label = "Revenue", color = 'g', linewidth = 1)
dx.plot(profit_plot.Time, profit_plot.Cumulative_COGS, label = "COGS", color = 'r', linewidth = 1)
dx.plot(profit_plot.Time, profit_plot.Cumulative_Wage_Expense, label = "Wage Expense", color = 'm', linewidth = 1)
dx.plot(profit_plot.Time, profit_plot.Cumulative_Profits, label = "Cumulative Profit", color = 'k', linewidth = 3)  
dx.yaxis.set_major_formatter('${x:,.0f}')
plt.legend()
plt.xlabel('Simulation Time (hrs)')
plt.ylabel('USD ($)')
plt.title('Profit/Loss vs Time')
plt.grid()
plt.show()

sim_days = g.sim_duration/24
total_orders = q_plot["Total_Orders"].max()
total_filled_orders = sum(order_plot.Revenue_Generated == g.wholesale_price*g.units_per_order)
total_late_orders = sum(order_plot.Revenue_Generated != g.wholesale_price*g.units_per_order)
on_time_fill_rate = 100*total_filled_orders/total_orders
order_process_mean = order_plot["Order_Process_Time"].mean()
order_process_service_level = order_plot["Order_Process_Time"].quantile(g.order_service_level)
revenue_generated = profit_plot["Cumulative_Revenue"].iat[-1]
cogs_generated = profit_plot["Cumulative_COGS"].iat[-1]
wage_generated = profit_plot["Cumulative_Wage_Expense"].iat[-1]
profit_generated = profit_plot["Cumulative_Profits"].iat[-1]
failed_tests= q_plot["Failed_Tests"].iat[-1]
gross_margin = 100*profit_generated/revenue_generated
print()
print("----------------------------------------------------------------")
print(f"                  After {sim_days:.1f} simulated days")    
print("----------------------------------------------------------------")
print(f"       Total Possible Orders:        {total_orders}")
print(f"       Total On-Time Orders:         {total_filled_orders}")
print(f"       Total Late Orders:            {total_late_orders}")
print(f"       On-Time Fill Rate:            {on_time_fill_rate:.2f}%")
print(f"       Failed Test Count:            {failed_tests}")
print(f"       Average Order Fill Time:      {order_process_mean:.2f} hours")
print(f"       {100*g.order_service_level:.0f}th percentile Fill Time:    {order_process_service_level:.2f} hours ")
print("----------------------------------------------------------------")
print(f"             Revenue:               ${revenue_generated:,.2f}")
print(f"             COGS:                  -${cogs_generated:,.2f}")
print(f"             Wage Expenses:         -${wage_generated:,.2f}")
print("                                    ---------------")
print(f"             Gross Profit:          ${profit_generated:,.2f}")
print(f"             Gross Margin:          {gross_margin:.2f}%")
print("----------------------------------------------------------------")
