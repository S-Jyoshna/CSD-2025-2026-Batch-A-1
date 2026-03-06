// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

contract LoanTable {
    struct Transaction {
        uint256 id;
        string username;
        uint256 monthlyamount;
        string method;
        string transaction_date;
        string status;
        string upi_id;
        string card_number;
        string wallet_name;
        string wallet_number;
    }

    mapping(address => Transaction[]) public transactions;


    function update_status(uint256 id, string memory status) public {
        Transaction[] storage tr = transactions[msg.sender];
        for (uint256 i = 0; i < tr.length; i++) {
            if (tr[i].id == id) {
                tr[i].status = status;
            }
        }
    }
    function addTransaction(
        string memory username,
        uint256 monthlyamount,
        string memory method,
        string memory transaction_date,
        string memory status,
        string memory upi_id,
        string memory card_number,
        string memory wallet_name,
        string memory wallet_number
    ) public {
        uint256 id = transactions[msg.sender].length;
        transactions[msg.sender].push(
            Transaction(
                id,
                username,
                monthlyamount,
                method,
                transaction_date,
                status,
                upi_id,
                card_number,
                wallet_name,
                wallet_number
            )
        );
    }

    function getTransactionData() public view returns (Transaction[] memory) {
    return transactions[msg.sender];
    }

}
