import React, { useState, useEffect } from 'react';
import { Card } from 'react-bootstrap';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import axios from 'axios';

const PayrollChart = () => {
  const [chartData, setChartData] = useState([]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await axios.get('http://localhost:8000/payroll/processing/history');
        
        // Group individual snapshots by date for the chart
        const grouped = response.data.reduce((acc, curr) => {
          // Format date as '09 Mar'
          const date = new Date(curr.processed_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
          acc[date] = (acc[date] || 0) + curr.net_pay;
          return acc;
        }, {});

        // Convert grouped object to array format required by Recharts
        const formattedData = Object.keys(grouped).map(key => ({
          name: key,
          value: grouped[key]
        })).reverse().slice(-7); // Last 7 days of data

        setChartData(formattedData);
      } catch (error) {
        console.error("Error fetching chart data:", error);
      }
    };
    fetchHistory();
  }, []);

  return (
    <Card className="border-0 shadow-sm p-4 mb-4 rounded-4">
      <h6 className="fw-bold mb-4" style={{ color: '#5A4343', fontSize: '13px' }}>PAYROLL HISTORY</h6>
      <div style={{ width: '100%', height: 280 }}>
        {chartData.length > 0 ? (
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
              <XAxis 
                dataKey="name" 
                axisLine={false} 
                tickLine={false} 
                tick={{fill: '#999', fontSize: 11}} 
              />
              <YAxis 
                axisLine={false} 
                tickLine={false} 
                tick={{fill: '#999', fontSize: 11}}
                tickFormatter={(value) => `₱${(value/1000).toFixed(0)}k`}
              />
              <Tooltip 
                cursor={{fill: 'rgba(210, 145, 145, 0.05)'}}
                contentStyle={{ borderRadius: '10px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: '12px' }}
                formatter={(value) => [`₱${value.toLocaleString()}`, 'Total Payout']}
              />
              <Bar 
                dataKey="value" 
                fill="#4B8B8B" 
                radius={[6, 6, 0, 0]} 
                barSize={40} 
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-100 d-flex align-items-center justify-content-center text-muted">
            <small>Insufficient data to generate history chart.</small>
          </div>
        )}
      </div>
    </Card>
  );
};

export default PayrollChart;
