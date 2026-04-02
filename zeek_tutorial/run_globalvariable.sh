sudo rm *.log

zeek -Cr data_aggregator.pcap ./dnp3m_analyzer/dnp3m-analyzer.hlto ./global_variable.zeek
