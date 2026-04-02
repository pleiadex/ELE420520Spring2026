
global num_dnp3m_data : count;

event zeek_init()
    {
    num_dnp3m_data = 0;
    print "Initialize global variable", num_dnp3m_data;
    }

event zeek_done()
    {
    print "We have observed ", num_dnp3m_data, " data";
    }

event dnp3m::request(c: connection, is_orig: bool, index: vector of count)
    {
    print "dnp3m request", c$id, is_orig, index;
    }

event dnp3m::response(c: connection, is_orig: bool)
    {
    print "dnp3m response", c$id, is_orig;
    }

event dnp3m::data(c: connection, is_orig: bool, index: count, measure: double)
    {
    print "dnp3m response", c$id, is_orig, index, measure;
    num_dnp3m_data = num_dnp3m_data + 1;
    }

